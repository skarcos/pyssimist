All tests in this folder start with the following imports:

```python
import sys
sys.path.append(<argument>)
```

This is to make it possible to run the tests without needing to create and use a virtual environment and install the module - just download.

The argument on the second line must point to the root directory of  the project, so that all libraries are
accessible. You will need to adjust depending on the location of the file. Some examples:


```python
# Eg when the test file is in the tests directory
import sys

sys.path.append("..")
```


```python
# Using a full path with os.path to make it os independent
import sys
from os import path
sys.path.append(path.join("c:\\" ,"Users", "Admin", "Documents", "pyssimist"))
```


```python
# Eg when the test file is in a subdirectory of tests directory
import sys
from os import path
sys.path.append(path.join("..", ".."))
```


```python
# When the test file is in the root project directory (pysimist) these lines might not be needed at all
# If we had to write them though they could look like this
import sys
sys.path.append(".")
```

