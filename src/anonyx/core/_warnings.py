import warnings
warnings.filterwarnings("ignore", message=".*invalid value encountered in divide.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")
