from __future__ import annotations

import copy
import warnings
from pathlib import Path
from typing import Any

from graph_pes.logger import logger


def create_from_data(thing: Any, type_msg: str | None = None) -> Any:
    if isinstance(thing, str):
        return create_from_string(thing)
    elif isinstance(thing, dict):
        return create_from_dict(thing)
    else:
        if type_msg is None:
            type_msg = f"Expected {thing} to be a string or a dictionary."
        raise TypeError(type_msg)


def _import(thing: str) -> Any:
    """
    Import a module or object from a fully qualified name.

    Example
    -------
    >>> _import("torch.nn.Tanh")
    <class 'torch.nn.modules.activation.Tanh'>
    """

    module_name, obj_name = thing.rsplit(".", 1)
    module = __import__(module_name, fromlist=[obj_name])
    return getattr(module, obj_name)


def warn_about_import_error(s: str):
    if not Path(s).exists():
        warnings.warn(
            f"Encountered a string ({s}) that looks like it "
            "could be meant to be imported - we couldn't do "
            "this. This may cause issues later.",
            stacklevel=2,
        )


def create_from_dict(d: dict[str, Any]) -> dict[str, Any] | Any:
    """
    Create objects from a dictionary.

    Two cases:
    1. ``d`` has a single key, and the value is a dictionary. In this case, we
       try to import the key (assuming it points to some callable), parse
       the value dictionary as keyword arguments and call the imported object
       with these arguments.
    2. leave the keys of ``d`` as they are, recursively create objects from
       the values and return the resulting dictionary.

    Parameters
    ----------
    d
        A dictionary.

    Returns
    -------
    dict[str, Any] | Any
        The resulting dictionary or object.

    Example
    -------
    A single-key dictionary with a dictionary value gets mapped to an object:

    >>> d = {"torch.nn.Linear": {"in_features": 10, "out_features": 20}}
    >>> create_from_dict(d)
    Linear(in_features=10, out_features=20, bias=True)

    A dictionary with multiple keys gets mapped to a dictionary:
    >>> d = {
    ...     "a": {"b": 1},
    ...     "c": "torch.nn.ReLU()",
    ... }
    >>> create_from_dict(d)
    {'a': {'b': 1}, 'c': ReLU()}

    Note that the string "torch.nn.ReLU()" is imported and called using this
    syntax.
    """
    return _create_from_dict(d, depth=0)


def _create_from_dict(d: dict[str, Any], depth: int) -> dict[str, Any] | Any:
    new_d = copy.deepcopy(d)

    def log(msg):
        logger.debug(f"create_from_dict: {'    ' * depth}{msg}")

    log(f"creating from {d}")

    # 1. recursively create objects from values
    for k, v in new_d.items():
        log(f"{k=}, {v=}")
        if isinstance(v, dict):
            log(f"recursing into {v=}")
            new_d[k] = _create_from_dict(v, depth + 1)
            log(f"received {new_d[k]}")

        elif isinstance(v, str) and looks_importable(v):
            try:
                log(f"trying to import '{v}'")
                obj = create_from_string(v)
                log(f"successfully imported {obj}")
                new_d[k] = obj

            except ImportError:
                log(f"failed to import '{v}'")
                warn_about_import_error(v)

    # 2. if dict has only one key, and that key maps to a dictionary of values
    #    try to import the key, call it with the values as kwargs and
    #    return the result. If any of this fails, return the dict as is.
    if len(new_d) == 1:
        k, kwargs = next(iter(new_d.items()))
        if isinstance(kwargs, dict) and looks_importable(k):
            log(
                "found a single-item dict with importable "
                f"key - trying to import '{k}' and call it with {kwargs}"
            )
            try:
                callable = _import(k)
                result = callable(**kwargs)
                log(f"successfully created {result}")
                log(f"final result: {result}")
                return result
            except ImportError:
                warn_about_import_error(k)

    # 3. if dict has more than one key, return it as is
    log(f"final result: {new_d}")
    return new_d


def looks_importable(s: str):
    return "." in s


def create_from_string(s: str):
    if s.endswith("()"):
        return _import(s[:-2])()
    else:
        return _import(s)