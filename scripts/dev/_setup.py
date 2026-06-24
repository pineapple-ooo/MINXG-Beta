"""Development environment setup."""
import subprocess, sys
subprocess.run([sys.executable,"-m","pip","install","-e",".[dev]"])
print("Dev environment ready!")
