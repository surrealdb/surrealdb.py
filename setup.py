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

install_command = """
cd /etc/yum.repos.d/ && 
sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* && 
sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* && 
yum install -y epel-release && 
yum install -y clang && 
yum install -y llvm-devel
"""

install_clang = subprocess.Popen(install_command, shell=True)
install_clang.wait()


# print("Installing libclang-dev...")
# install_gcc = subprocess.Popen("yum install -y git cmake gcc gcc-c++ python3", shell=True)
# install_gcc.wait()

# mkdir = subprocess.Popen("mkdir ~/llvm-project", shell=True)
# mkdir.wait()

# clone_llvm = subprocess.Popen("cd ~/llvm-project && git clone https://github.com/llvm/llvm-project.git", shell=True)
# clone_llvm.wait()

# CD_PROJECT = "cd ~/llvm-project/llvm-project"
# mkdir = subprocess.Popen(f"{CD_PROJECT} && mkdir build", shell=True)
# mkdir.wait()

# CD_PROJECT = "cd ~/llvm-project/llvm-project/build"
# cmake = subprocess.Popen(f'{CD_PROJECT} && cmake -G "Unix Makefiles" ../llvm -DCMAKE_BUILD_TYPE=Release', shell=True)
# cmake.wait()

# make = subprocess.Popen(f"{CD_PROJECT} && make -j$(nproc)", shell=True)
# make.wait()

# make_install = subprocess.Popen(f"{CD_PROJECT} && make install", shell=True)
# make_install.wait()


# install_llvm = subprocess.Popen("yum install -y clang", shell=True)
# install_llvm.wait()
# update_llvm = subprocess.Popen("yum update clang", shell=True)
# update_llvm.wait()


# user_lib_ls = subprocess.check_output(["ls", "/usr/lib/"]).decode().strip()
# print(f"user_lib_ls: {user_lib_ls}")

# clang_version = subprocess.check_output(["clang", "--version"]).decode().strip()
# print(f"\n\n\n\n\nclang_version: {clang_version}\n\n\n\n\n")

# import glob

# file_patterns = ['libclang.so', 'libclang-*.so', 'libclang.so.*', 'libclang-*.so.*']
# file_paths = []

# for pattern in file_patterns:
#     matching_files = glob.glob(pattern)
#     file_paths.extend(matching_files)

# print("file_paths from python:")
# for i in file_paths:
#     print(i)


# user_lib_ls = subprocess.check_output(["ls", "/usr/lib/clang/3.4.2/"]).decode().strip()
# print(f"clang_lib_ls: {user_lib_ls}")


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

# print("configuring llvm...")
# # exporting the path of llvm
# export_command = f"export PATH=$PATH:/usr/lib/llvm-13/bin/"
# export_path = subprocess.Popen([export_command], shell=True)
# export_path.wait()
# print("configuring llvm... Done")

print("installing clang...")
# Get the LLVM library path
# llvm_lib_path = subprocess.check_output(["llvm-config", "--libdir"]).decode().strip()

# Set the LIBCLANG_PATH environment variable
# os.environ["LIBCLANG_PATH"] = "/usr/lib/clang/"
# print("installing clang... Done")


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