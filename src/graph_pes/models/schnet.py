from __future__ import annotations

import torch

from graph_pes.graphs import AtomicGraph
from graph_pes.graphs.operations import (
    index_over_neighbours,
    neighbour_distances,
    sum_over_neighbours,
)
from graph_pes.models.scaling import AutoScaledPESModel
from graph_pes.nn import MLP, PerElementEmbedding, ShiftedSoftplus
from graph_pes.util import uniform_repr

from .distances import DistanceExpansion, GaussianSmearing


class CFConv(torch.nn.Module):
    r"""
    CFConv: The Continous Filter Convolution

    Originally proposed as part of `SchNet <https://arxiv.org/abs/1706.08566>`_,
    this message passing layer creates messages of the form:

    .. math::
        m_{ij} = x_j \odot \mathbb{F}(r_{ij})

    where :math:`\mathbb{F}` is some learnable filter function which
    expands the radial distance :math:`r_{ij}` into a set of features
    that match the dimensionality of the node features :math:`x_j`.

    Example
    -------
    .. code::

        from graph_pes.models.distances import GaussianSmearing
        from graph_pes.nn import MLP
        from torch import nn

        filter_generator = nn.Sequential(
            GaussianSmearing(8, 5.0),
            MLP([8, 16, 16, 8]),
        )
        cfconv = CFConv(filter_generator)

    Parameters
    ----------
    filter_generator
        The filter function :math:`\mathbb{F}`.
    """

    def __init__(self, filter_generator: torch.nn.Module):
        super().__init__()
        self.filter_generator = filter_generator

    def forward(
        self,
        node_features: torch.Tensor,  # (n_atoms, F)
        edge_distances: torch.Tensor,  # (E,)
        graph: AtomicGraph,
    ) -> torch.Tensor:  # (n_atoms, F)
        edge_features = self.filter_generator(edge_distances)  # (E, F)
        neighbour_features = index_over_neighbours(
            node_features, graph
        )  # (E, F)

        messages = neighbour_features * edge_features  # (E, F)

        return sum_over_neighbours(messages, graph)

    def __repr__(self):
        rep = f"CFConv({self.filter_generator})"
        if len(rep) > 40:
            indented = "  " + "\n  ".join(
                str(self.filter_generator).split("\n")
            )
            rep = f"CFConv(\n{indented}\n)"
        return rep


class SchNetInteraction(torch.nn.Module):
    r"""
    SchNet interaction block.

    Updates the embedding of each atom, :math:`x_i` by sequentially
    applying the following:

    1. a linear transform of each node's features :math:`x_i \leftarrow W x_i`
    2. message creation :math:`m_{ij} = x_j \odot \mathbb{F}(r_{ij})`
    3. message aggregation
       :math:`m_i = \sum_{j \in \mathcal{N}(i)} m_{ij}`
    4. a multi-layer perceptron that further embeds these new node features
       :math:`x_i \leftarrow \mathrm{MLP}(h_i)`

    Parameters
    ----------
    n_features
        Number of features per node.
    expansion_features
        Number of features used for the radial basis expansion.
    cutoff
        Neighborhood cutoff radius.
    basis_type
        The type of radial basis expansion to use.
    """

    def __init__(
        self,
        node_features: int,
        expansion_features: int,
        cutoff: float,
        basis_type: type[DistanceExpansion],
    ):
        super().__init__()

        # schnet interaction block's are composed of 3 elements

        # 1. linear transform to get new node features
        self.linear = torch.nn.Linear(node_features, node_features, bias=False)

        # 2. cfconv to mix these new features with distances information,
        # and aggregate over neighbors to create completely new node features
        filter_generator = torch.nn.Sequential(
            basis_type(expansion_features, cutoff),
            MLP(
                [expansion_features, node_features, node_features],
                activation=ShiftedSoftplus(),
            ),
        )
        self.cfconv = CFConv(filter_generator)

        # 3. mlp to further embed these new node features
        self.mlp = MLP(
            [node_features, node_features, node_features],
            activation=ShiftedSoftplus(),
        )

    def forward(
        self,
        node_features: torch.Tensor,
        neighbour_distances: torch.Tensor,
        graph: AtomicGraph,
    ):
        # 1. linear transform to get new node features
        h = self.linear(node_features)

        # 2. cfconv to mix these new features with distances information,
        # and aggregate over neighbors to create completely new node features
        h = self.cfconv(h, neighbour_distances, graph)

        # 3. mlp to further embed these new node features
        return self.mlp(h)


class SchNet(AutoScaledPESModel):
    r"""
    The `SchNet <https://arxiv.org/abs/1706.08566>`_ model: a pairwise, scalar,
    message passing GNN.

    A stack of :class:`SchNetInteraction` blocks are used to update
    the node features of each atom, :math:`x_i` by sequentially
    aggregating over neighbouring atom's features, :math:`x_j`:, and
    distances, :math:`r_{ij}`:.

    Citation:

    .. code:: bibtex

        @article{Schutt-18-03,
            title = {{{SchNet}} {\textendash} {{A}} Deep Learning Architecture for Molecules and Materials},
            author = {Sch{\"u}tt, K. T. and Sauceda, H. E. and Kindermans, P.-J. and Tkatchenko, A. and M{\"u}ller, K.-R.},
            year = {2018},
            journal = {The Journal of Chemical Physics},
            volume = {148},
            number = {24},
            pages = {241722},
            doi = {10.1063/1.5019779},
        }

    Parameters
    ----------
    node_features
        Number of features per node.
    expansion_features
        Number of features used for the radial basis expansion.
    cutoff
        Neighborhood cutoff radius.
    layers
        Number of interaction blocks to apply.
    expansion
        The type of radial basis expansion to use. Defaults to
        :class:`GaussianSmearing <graph_pes.models.distances.GaussianSmearing>`
        as in the original paper.
    """  # noqa: E501

    def __init__(
        self,
        node_features: int = 64,
        expansion_features: int = 50,
        cutoff: float = 5.0,
        layers: int = 3,
        expansion: type[DistanceExpansion] | None = None,
    ):
        super().__init__()

        self.cutoff = cutoff

        if expansion is None:
            expansion = GaussianSmearing

        self.chemical_embedding = PerElementEmbedding(node_features)

        self.interactions = torch.nn.ModuleList(
            SchNetInteraction(
                node_features, expansion_features, cutoff, expansion
            )
            for _ in range(layers)
        )

        self.read_out = MLP(
            [node_features, node_features // 2, 1],
            activation=ShiftedSoftplus(),
        )

    def predict_unscaled_energies(self, graph: AtomicGraph) -> torch.Tensor:
        h = self.chemical_embedding(graph["atomic_numbers"])
        d = neighbour_distances(graph)

        for interaction in self.interactions:
            h = h + interaction(h, d, graph)

        return self.read_out(h)

    def __repr__(self) -> str:
        return uniform_repr(
            self.__class__.__name__,
            chemical_embedding=self.chemical_embedding,
            interactions=self.interactions,
            read_out=self.read_out,
            per_element_scaling=self.per_element_scaling,
        )
