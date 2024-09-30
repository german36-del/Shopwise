import contextlib
import re
import sys
from difflib import get_close_matches
from typing import Dict, List

from shopwise.utils import DEFAULT_CFG, LOGGER, colorstr, load_config

TASKS = ["supermarket"]

CLI_HELP_MSG = f"""
    Arguments received: {str(['shopwise'] + sys.argv[1:])}. shopwise commands use the following syntax:

        shopwise TASK ARGS

        Where   TASK (optional) is one of {" and ".join(TASKS)}.
                ARGS (optional) are any number of custom 'arg=value' pairs that override default configuration.
                    See all ARGS at shopwise/cfg folder

    1.  (supermarket) Compute which supermarket is more suited for you with your supermarket

    GitHub: #TODO: Complete
    """


def check_dict_alignment(base: Dict, custom: Dict, e=None):
    """
    Checks for any mismatched keys between a custom configuration dictionary
    and a base configuration dictionary. If any mismatched keys are found,
    the function prints out similar keys from the base dictionary and raises
    a SyntaxError.

    Args:
        base (dict): A dictionary of base configuration options.
        custom (dict): A dictionary of custom configuration options.
        e (Exception, optional): An optional exception to raise from (default is None).

    Raises:
        SyntaxError: If mismatched keys are found between the custom and base dictionaries.
    """
    base_keys, custom_keys = (set(x.keys()) for x in (base, custom))
    mismatched = [k for k in custom_keys if k not in base_keys]
    if mismatched:
        string = ""
        for x in mismatched:
            matches = get_close_matches(x, base_keys)  # key list
            matches = [
                f"{k}={base[k]}" if base.get(k) is not None else k for k in matches
            ]
            match_str = f"Similar arguments are i.e. {matches}." if matches else ""
            string += (
                f"'{colorstr('red', 'bold', x)}' is not a valid argument. {match_str}\n"
            )
        raise SyntaxError(string + CLI_HELP_MSG) from e


def smart_value(v):
    """
    Convert a string to an underlying type such as int, float, bool, etc.

    This function evaluates a string and attempts to convert it into its
    respective Python type. It can handle strings that represent `None`,
    `True`, and `False`, as well as numeric types. If the string cannot
    be converted, it will be returned as-is.

    Args:
        v (str): The string to be evaluated and converted.

    Returns:
        int | float | bool | None | str: The converted value or the original
        string if conversion is not possible.
    """
    if v.lower() == "none":
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    with contextlib.suppress(Exception):
        return eval(v)
    return v


def parse_key_value_pair(pair):
    """
    Parse one 'key=value' pair and return the key and value.

    This function processes a string in the format 'key=value', ensuring that
    any spaces around the equals sign are removed. It splits the string into
    key and value components and checks that the value is not empty.

    Args:
        pair (str): A string representing a key-value pair in the format 'key=value'.

    Returns:
        tuple: A tuple containing the key (str) and the value (smart_value type).
    """
    pair = re.sub(r" *= *", "=", pair)
    k, v = pair.split("=", 1)
    assert v, f"missing '{k}' value"
    return k, smart_value(v)


def merge_equals_args(args: List[str]) -> List[str]:
    """
    Merges arguments around isolated '=' args in a list of strings.

    This function processes a list of string arguments and merges them based on specific
    conditions related to the presence of isolated '=' characters. It handles cases where
    the first argument ends with '=', the second starts with '=', and when '=' is found
    in the middle of the arguments.

    Args:
        args (List[str]): A list of strings where each element is an argument.

    Returns:
        List[str]: A list of strings where the arguments around isolated '=' are merged.
    """
    new_args = []
    for i, arg in enumerate(args):
        if arg == "=" and 0 < i < len(args) - 1:
            new_args[-1] += f"={args[i + 1]}"
            del args[i + 1]
        elif arg.endswith("=") and i < len(args) - 1 and "=" not in args[i + 1]:
            new_args.append(f"{arg}{args[i + 1]}")
            del args[i + 1]
        elif arg.startswith("=") and i > 0:
            new_args[-1] += arg
        else:
            new_args.append(arg)
    return new_args


def entrypoint(debug=""):
    """
    Parse CLI input and execute the entrypoint with specified arguments.

    This function processes a debug string or command-line arguments to update
    configuration settings and task values before initializing a ShopWise
    object. It supports special commands and handles configuration overrides
    based on user input.

    Args:
        debug (str, optional): CLI debug string comprising 'cfg' key-value pairs.
            Defaults to "".

    Returns:
        ShopWise: An instance of ShopWise initialized with the provided arguments.
    """
    args = (debug.split(" ") if debug else sys.argv)[1:]
    if not args:
        LOGGER.info(CLI_HELP_MSG)
        return

    special = {
        "help": lambda: LOGGER.info(CLI_HELP_MSG),
    }
    full_args_dict = {
        **DEFAULT_CFG,
        **{k: None for k in TASKS},
        **special,
    }
    special.update({k[0]: v for k, v in special.items()})
    special.update(
        {k[:-1]: v for k, v in special.items() if len(k) > 1 and k.endswith("s")}
    )
    special = {
        **special,
        **{f"-{k}": v for k, v in special.items()},
        **{f"--{k}": v for k, v in special.items()},
    }
    overrides = {}
    for a in merge_equals_args(args):
        if a.startswith("--"):
            LOGGER.warning(
                colorstr(
                    "yellow",
                    "WARNING ⚠️ '%s' does not require leading dashes '--', \
                    updating to '%s'."s'.",
                    a,
                    a[2:],
                )
            )
            a = a[2:]
        if a.endswith(","):
            LOGGER.warning(
                colorstr(
                    "yellow",
                    "WARNING ⚠️ '%s' does not require trailing comma ',', updating to '%s.",
                    a,
                    a[2:],
                )
            )
            a = a[:-1]
        if "=" in a:
            try:
                k, v = parse_key_value_pair(a)
                if k == "cfg":  # custom.yaml passed
                    LOGGER.info("Overriding %s with %s", DEFAULT_CFG, v)
                    overrides = {
                        k: val for k, val in load_config(v).items() if k != "cfg"
                    }
                else:
                    overrides[k] = v
            except (NameError, SyntaxError, ValueError, AssertionError) as e:
                check_dict_alignment(full_args_dict, {a: ""}, e)
        elif a in TASKS:
            overrides["task"] = a
        elif a.lower() in special:
            special[a.lower()]()
            return
        elif a in DEFAULT_CFG and isinstance(DEFAULT_CFG[a], bool):
            overrides[a] = True
        elif a in DEFAULT_CFG:
            raise SyntaxError(
                f"'{colorstr('red', 'bold', a)}' is a valid shopwise argument but is missing \
                an '=' sign to set its value, i.e. try '{a}={DEFAULT_CFG[a]}'\n{CLI_HELP_MSG}"
            )
        else:
            check_dict_alignment(full_args_dict, {a: ""})
    check_dict_alignment(full_args_dict, overrides)
    for k, v in DEFAULT_CFG.items():
        if overrides.get(k, None) is None:
            overrides[k] = v
    task = overrides.pop("task", None)
    if task is None:
        task = DEFAULT_CFG["task"] or "project"
        LOGGER.warning(
            colorstr(
                "yellow",
                f"WARNING ⚠️ 'task' is missing. Valid tasks are {TASKS}    . \
                Using default 'task=project'.ct'.",
            )
        )
    if task:
        if task not in TASKS:
            raise ValueError(
                f"Invalid 'task={task}'. Valid tasks are {TASKS}.\n{CLI_HELP_MSG}"
            )
    from shopwise.engine import ShopWise

    ShopWise(task, **overrides)
