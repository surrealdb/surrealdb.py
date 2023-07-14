#!/usr/bin/env python
from setuptools import setup
from setuptools_rust import Binding, RustExtension

import os
import subprocess

# get_command = "apt-get"
get_command = "yum"

# print("Updating apt-get...")
# # Update apt-get
# update_apt = subprocess.Popen([get_command, "update"], shell=True)
# update_apt.wait()
# print("Updating apt-get... Done")

# print("Installing llvm...")
# # Install LLVM using apt-get
# install_llvm = subprocess.Popen([get_command, "install", "-y", "llvm-dev"], shell=True)
# install_llvm.wait()
# print("Installing llvm... Done")


# print("Installing clang...")
# install_llvm = subprocess.Popen([get_command, "install", "-y", "clang"], shell=True)
# install_llvm.wait()
# print("Installing clang... Done")


print("Installing libclang-dev...")
install_llvm = subprocess.Popen("apt-get update && apt-get install -y clang", shell=True)
install_llvm.wait()


user_lib_ls = subprocess.check_output(["ls", "/usr/lib/"]).decode().strip()
print(f"user_lib_ls: {user_lib_ls}")


# print("Installing llvmlite...")
# # Install LLVM using pip
# install_llvm = subprocess.Popen(["sudo pip3 install llvmlite"], shell=True)
# install_llvm.wait()
# print("Installing llvmlite... Done")

# print("getting llvm version...")
# getting the version of llvm
# llvm_version: str = subprocess.check_output(["dpkg -l | grep llvm"]).decode().strip()
# print("getting llvm version... Done")
# print(f"llvm version: {llvm_version}")

print("configuring llvm...")
# exporting the path of llvm
export_command = f"export PATH=$PATH:/usr/lib/llvm-13/bin/"
export_path = subprocess.Popen([export_command], shell=True)
export_path.wait()
print("configuring llvm... Done")

print("installing clang...")
# Get the LLVM library path
# llvm_lib_path = subprocess.check_output(["llvm-config", "--libdir"]).decode().strip()

# Set the LIBCLANG_PATH environment variable
os.environ["LIBCLANG_PATH"] = "/usr/lib/llvm-13/bin/"
print("installing clang... Done")


setup(
    name="surrealdb",
    version="1.0",
    rust_extensions=[RustExtension("surrealdb.rust_surrealdb", binding=Binding.PyO3)],
    packages=[
        "surrealdb", 
        "surrealdb.models",
        "surrealdb.execution_mixins"
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)