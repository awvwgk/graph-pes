from typing import Literal

import numpy as np
import pytest

from graph_pes.atomic_graph import number_of_atoms
from graph_pes.data import load_atoms_dataset
from graph_pes.data.datasets import file_dataset

from .. import helpers


@pytest.mark.parametrize("split", ["random", "sequential"])
def test_shuffling(split: Literal["random", "sequential"]):
    dataset = load_atoms_dataset(
        id=helpers.CU_STRUCTURES_FILE,
        cutoff=3.7,
        n_train=8,
        n_valid=2,
        split=split,
    )

    if split == "sequential":
        np.testing.assert_allclose(
            dataset.train[0].R,
            helpers.CU_TEST_STRUCTURES[0].positions,
        )
    else:
        # different structures with different sizes in the first
        # position of the training set after shuffling
        assert number_of_atoms(dataset.train[0]) != len(
            helpers.CU_TEST_STRUCTURES[0]
        )


def test_dataset():
    dataset = load_atoms_dataset(
        id=helpers.CU_STRUCTURES_FILE,
        cutoff=3.7,
        n_train=8,
        n_valid=2,
    )

    assert len(dataset.train) == 8
    assert len(dataset.valid) == 2


def test_property_map():
    dataset = load_atoms_dataset(
        id=helpers.CU_STRUCTURES_FILE,
        cutoff=3.7,
        n_train=8,
        n_valid=2,
        property_map={"positions": "forces"},
        split="sequential",
    )

    assert "forces" in dataset.train[0].properties
    np.testing.assert_allclose(
        dataset.train[0].properties["forces"],
        helpers.CU_TEST_STRUCTURES[0].positions,
    )

    with pytest.raises(
        ValueError, match="Unable to find properties: {'UNKNOWN KEY'}"
    ):
        load_atoms_dataset(
            id=helpers.CU_STRUCTURES_FILE,
            cutoff=3.7,
            n_train=8,
            n_valid=2,
            property_map={"UNKNOWN KEY": "energy"},
        )


def test_file_dataset():
    dataset = file_dataset(
        helpers.CU_STRUCTURES_FILE,
        cutoff=2.5,
        n=5,
        shuffle=False,
        seed=42,
    )

    assert len(dataset) == 5

    shuffled = file_dataset(
        helpers.CU_STRUCTURES_FILE,
        cutoff=2.5,
        n=5,
        shuffle=True,
        seed=42,
    )

    assert len(shuffled) == 5
    assert shuffled[0].R.shape != dataset[0].R.shape
