"""Where the project is: the folder that holds src/, work/, assets/, audio/, fonts/ and out/.

Found from this file's own location, so a copied project works wherever it lives; set MM_ROOT to point elsewhere."""
import os

ROOT = (os.environ.get("MM_ROOT")
        or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))).replace("\\", "/")
