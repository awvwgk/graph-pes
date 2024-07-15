from __future__ import annotations

from typing import Callable

import pytest
import pytorch_lightning
from graph_pes.core import GraphPESModel
from graph_pes.models import ALL_MODELS, OneHotNequIP


def all_model_factories(
    expected_elements: list[str],
) -> tuple[list[str], list[Callable[[], GraphPESModel]]]:
    pytorch_lightning.seed_everything(42)
    required_kwargs = {OneHotNequIP: {"elements": expected_elements}}

    def _model_factory(
        model_klass: type[GraphPESModel],
    ) -> Callable[[], GraphPESModel]:
        return lambda: model_klass(**required_kwargs.get(model_klass, {}))

    names = [model.__name__ for model in ALL_MODELS]
    factories = [_model_factory(model) for model in ALL_MODELS]
    return names, factories


def all_models(
    expected_elements: list[str],
) -> tuple[list[str], list[GraphPESModel]]:
    names, factories = all_model_factories(expected_elements)
    return names, [factory() for factory in factories]


def parameterise_all_models(
    expected_elements: list[str],
):
    def decorator(func):
        names, models = all_models(expected_elements)
        return pytest.mark.parametrize("model", models, ids=names)(func)

    return decorator


def parameterise_model_classes(
    expected_elements: list[str],
):
    def decorator(func):
        names, factories = all_model_factories(expected_elements)
        return pytest.mark.parametrize("model_class", factories, ids=names)(
            func
        )

    return decorator