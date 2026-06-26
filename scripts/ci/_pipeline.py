"""CI pipeline automation."""
import subprocess, sys, os
def run_tests(): subprocess.run(["python","-m","pytest","tests/","-v","--tb=short"])
def run_lint(): subprocess.run(["python","-m","py_compile"]+[f for f in os.listdir(".") if f.endswith(".py")])
if __name__=="__main__":
    run_lint(); print("---"); run_tests()
