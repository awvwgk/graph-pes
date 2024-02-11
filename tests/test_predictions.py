import pytest
import torch
from ase import Atoms
from graph_pes.data import AtomicGraphBatch, convert_to_atomic_graph
from graph_pes.models.pairwise import LennardJones
from graph_pes.util import Property

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
        Property.ENERGY: (),
        Property.FORCES: (2, 3),
        Property.STRESS: (3, 3),
    }

    model = LennardJones()

    # by default, get_predictions returns energy and forces on
    # structures with no cell:
    predictions = model.predict(no_pbc)
    assert set(predictions.keys()) == {"energy", "forces"}

    for key in Property.ENERGY, Property.FORCES:
        assert predictions[key].shape == expected_shapes[key]

    # if we ask for stress, we get an error:
    with pytest.raises(KeyError):
        model.predict(no_pbc, property="stress")

    # with pbc structures, we should get all three predictions
    predictions = model.predict(pbc)
    assert set(predictions.keys()) == {"energy", "forces", "stress"}

    for key in Property.ENERGY, Property.FORCES, Property.STRESS:
        assert predictions[key].shape == expected_shapes[key]


def test_batched_prediction():
    batch = AtomicGraphBatch.from_graphs([pbc, pbc])

    expected_shapes = {
        Property.ENERGY: (2,),  # two structures
        Property.FORCES: (4, 3),  # four atoms
        Property.STRESS: (2, 3, 3),  # two structures
    }

    predictions = LennardJones().predict(batch)

    for key in Property.ENERGY, Property.FORCES, Property.STRESS:
        assert predictions[key].shape == expected_shapes[key]


def test_isolated_atom():
    atom = Atoms("H", positions=[(0, 0, 0)], pbc=False)
    graph = convert_to_atomic_graph(atom, cutoff=1.5)
    assert graph.n_edges == 0

    predictions = LennardJones().predict(graph)
    assert torch.allclose(predictions["forces"], torch.zeros(1, 3))
