"""
Simplified file saving utility without iopath dependency.
"""

import json
import pickle
import yaml
import numpy as np
import logging
import os

def save_file(data, filename, append_to_json=True, verbose=True):
    """
    Common i/o utility to handle saving data to various file formats.
    Supported:
        .pkl, .pickle, .npy, .json
    Specifically for .json, users have the option to either append (default)
    or rewrite by passing in Boolean value to append_to_json.
    """

    if verbose:
        logging.info(f"Saving data to file: {filename}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    file_ext = os.path.splitext(filename)[1]
    if file_ext in [".pkl", ".pickle"]:
        with open(filename, "wb") as fopen:
            pickle.dump(data, fopen, pickle.HIGHEST_PROTOCOL)
    elif file_ext == ".npy":
        with open(filename, "wb") as fopen:
            np.save(fopen, data)
    elif file_ext == ".json":
        if append_to_json:
            with open(filename, "a") as fopen:
                fopen.write(json.dumps(data, sort_keys=True) + "\n")
                fopen.flush()
        else:
            with open(filename, "w") as fopen:
                fopen.write(json.dumps(data, sort_keys=True) + "\n")
                fopen.flush()
    elif file_ext == ".yaml":
        with open(filename, "w") as fopen:
            dump = yaml.dump(data)
            fopen.write(dump)
            fopen.flush()
    else:
        raise Exception(f"Saving {file_ext} is not supported yet")

    if verbose:
        logging.info(f"Saved data to file: {filename}")