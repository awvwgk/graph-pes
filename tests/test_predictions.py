from __future__ import annotations

import pytest
import torch
from ase import Atoms
from graph_pes.data import (
    batch_graphs,
    convert_to_atomic_graph,
    keys,
    number_of_edges,
)
from graph_pes.models.pairwise import LennardJones

no_pbc = convert_to_atomic_graph(
    Atoms("H2", positions=[(0, 0, 0), (0, 0, 1)], pbc=False),
    cutoff=1.5,
)
pbc = convert_to_atomic_graph(
    Atoms("H2", positions=[(0, 0, 0), (0, 0, 1)], pbc=True, cell=(2, 2, 2)),
    cutoff=1.5,
)


def test_predictions():
    expected_shapes = {
        keys.ENERGY: (),
        keys.FORCES: (2, 3),
        keys.STRESS: (3, 3),
    }

    model = LennardJones()

    # by default, get_predictions returns energy and forces on
    # structures with no cell:
    predictions = model.predict(no_pbc)
    assert set(predictions.keys()) == {"energy", "forces"}

    for key in keys.ENERGY, keys.FORCES:
        assert predictions[key].shape == expected_shapes[key]

    # if we ask for stress, we get an error:
    with pytest.raises(KeyError):
        model.predict(no_pbc, property="stress")

    # with pbc structures, we should get all three predictions
    predictions = model.predict(pbc)
    assert set(predictions.keys()) == {"energy", "forces", "stress"}

    for key in keys.ENERGY, keys.FORCES, keys.STRESS:
        assert predictions[key].shape == expected_shapes[key]


def test_batched_prediction():
    batch = batch_graphs([pbc, pbc])

    expected_shapes = {
        keys.ENERGY: (2,),  # two structures
        keys.FORCES: (4, 3),  # four atoms
        keys.STRESS: (2, 3, 3),  # two structures
    }

    predictions = LennardJones().predict(batch)

    for key in keys.ENERGY, keys.FORCES, keys.STRESS:
        assert predictions[key].shape == expected_shapes[key]


def test_isolated_atom():
    atom = Atoms("H", positions=[(0, 0, 0)], pbc=False)
    graph = convert_to_atomic_graph(atom, cutoff=1.5)
    assert number_of_edges(graph) == 0

    predictions = LennardJones().predict(graph)
    assert torch.allclose(predictions["forces"], torch.zeros(1, 3))
