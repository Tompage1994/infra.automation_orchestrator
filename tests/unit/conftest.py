import os
import sys

COLLECTION_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
REPO_ROOT = os.path.dirname(COLLECTION_ROOT)
ANSIBLE_COLLECTIONS = os.path.join(REPO_ROOT, "ansible_collections")

for path in (REPO_ROOT, ANSIBLE_COLLECTIONS):
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)
