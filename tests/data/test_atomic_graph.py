import numpy as np
import pytest
import torch
from ase import Atoms
from graph_pes.data.atomic_graph import (
    AtomicGraph,
    convert_to_atomic_graph,
    convert_to_atomic_graphs,
    extract_information,
)

ISOLATED_ATOM = Atoms("H", positions=[(0, 0, 0)], pbc=False)
PERIODIC_ATOM = Atoms("H", positions=[(0, 0, 0)], pbc=True, cell=(1, 1, 1))
RANDOM_STRUCTURE = Atoms(
    "H8",
    positions=np.random.RandomState(42).rand(8, 3),
    pbc=True,
    cell=np.eye(3),
)
STRUCTURES = [ISOLATED_ATOM, PERIODIC_ATOM, RANDOM_STRUCTURE]
GRAPHS = convert_to_atomic_graphs(STRUCTURES, cutoff=1.0)


@pytest.mark.parametrize("structure, graph", zip(STRUCTURES, GRAPHS))
def test_general(structure, graph):
    assert isinstance(graph, AtomicGraph)
    assert graph.n_atoms == len(structure)

    n_edges = graph.n_edges
    assert n_edges == graph.neighbour_index.shape[1]
    assert n_edges == graph.neighbour_vectors.shape[0]
    assert n_edges == graph.neighbour_distances.shape[0]


def test_iso_atom():
    graph = convert_to_atomic_graph(ISOLATED_ATOM, cutoff=1.0)
    assert graph.n_atoms == 1
    assert graph.n_edges == 0


def test_periodic_atom():
    graph = convert_to_atomic_graph(PERIODIC_ATOM, cutoff=1.1)
    assert graph.n_atoms == 1

    # 6 neighbours: up, down, left, right, front, back
    assert graph.n_edges == 6


def test_random_structure():
    graph = convert_to_atomic_graph(RANDOM_STRUCTURE, cutoff=1.0)
    assert graph.n_atoms == 8

    assert np.linalg.norm(graph.neighbour_vectors, axis=-1).max() <= 1.0


def test_warning_on_position():
    # check that a warning is raised if the user tries to access the positions
    # directly for a structure with a unit cell
    with pytest.warns(UserWarning):
        _ = GRAPHS[1].positions


def test_device_casting():
    # check that the graph can be moved to a device
    graph = GRAPHS[0]
    cpu_graph = graph.to("cpu")
    assert cpu_graph is not graph
    assert cpu_graph._positions.device == torch.device("cpu")


def test_extract_information():
    atoms = Atoms("H2", positions=[(0, 0, 0), (0, 0, 1)], pbc=False)
    atoms.info["energy"] = -1.0
    atoms.arrays["forces"] = np.zeros((2, 3))

    # test defaults (all information extracted)
    atom_info, structure_info = extract_information(atoms)
    assert structure_info["energy"] == -1.0
    assert atom_info["forces"].shape == (2, 3)
    for key in ["numbers", "positions", "cell", "pbc"]:
        assert key not in atom_info
        assert key not in structure_info

    # test explicit keys
    atom_info, structure_info = extract_information(
        atoms, structure_keys=["energy"], atom_keys=[]
    )
    assert structure_info["energy"] == -1.0
    assert "forces" not in atom_info

    # test error on missing keys
    with pytest.raises(KeyError):
        extract_information(atoms, structure_keys=["missing"])

    # error if we explicitly ask for a non-tensor key
    atoms.info["string"] = "test"
    with pytest.raises(ValueError):
        extract_information(atoms, structure_keys=["string"])


def test_isolated_api():
    graph = AtomicGraph.from_isolated_structure(
        Z=torch.tensor([1, 1]),
        positions=torch.tensor([[0, 0, 0], [0, 0, 1]]),
        neighbour_index=torch.tensor([[0, 1], [1, 0]]),
    )
    assert graph.n_atoms == 2, "unexpected graph created"
    assert not graph.has_cell, "graph should not have a cell"