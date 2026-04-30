# CS706 Project: VersiCode-Exe
## Overview
This repository contains the VersiCode-Exe dataset. We build upon the VersiCode repository provided by the authors of VersiCode: Towards Version-controllable Code Generation. The original code repository of VersiCode can be found here https://github.com/wutong8023/VersiCode.git.

## Resources
Please clone the Repository via `git clone https://github.com/orangeguppy/VersiCode-Exe` to download our code and dataset before proceeding with the next steps below.

## Usage: VersiCode-Exe Dataset Files
As our work extends the VersiCode dataset, we retain all fields in the original VersiCode dataset. Our dataset files can be found in the ```VersiCode_Exe``` folder. We add our own field to each data row with the following schema:

```
"run_result": {
  "status": "string",              // Overall execution status (e.g. "ok", "error")
  "stdout": "string",              // Output produced during execution
  "stderr": "string",              // Error output (if any)
  "exit_code": "int",              // Exit code (0 means ok)
  "timeout": "boolean",            // If execution timed out
  "successful_env": "string",      // Environment config where execution succeeded
  "attempts": [
    {
      "env_name": "string",        // Name of execution environment
      "stdout": "string",          // Output from this attempt
      "stderr": "string",          // Error output from this attempt
      "exit_code": "int",          // Exit code for this attempt
      "timeout": "boolean"         // Whether this attempt timed out
    }
  ]
}
```

## Usage: Verifying VersiCode-Exe Dataset Rows
To validate the execution of each VersiCode-Exe sample on its assigned native Python environment, run ```python util/verify_dataset.py```. The validation results can be viewed in the ```code_field_validation_results``` folder. This script will also print out the number of verified samples per category as shown in Table 6 of the report.

To brute-force execute each VersiCode Code Completion dataset row on each of the four defined environment configurations listed in ```versicode_env_configs.json```, run ```python util/run_code_field_samples.py```. The brute-force execution results can be view in the ```code_field_run_results``` folder.

## Usage: Computing dataset statistics
To compute the distribution of environment configurations in Table 7 of the report, run ```python util/print_env_distribution_entries.py```.

## References
```
@article{versicode,
  author={Tongtong Wu and Weigang Wu and Xingyu Wang and Kang Xu and Suyu Ma and Bo Jiang and Ping Yang and Zhenchang Xing and Yuan-Fang Li and Gholamreza Haffari},
  title        = {VersiCode: Towards Version-controllable Code Generation},
  journal      = {CoRR},
  volume       = {abs/2406.07411},
  year         = {2024},
  url          = {https://arxiv.org/abs/2406.07411},
}
```