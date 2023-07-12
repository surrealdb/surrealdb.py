#!/usr/bin/env python
from setuptools import setup
from setuptools_rust import Binding, RustExtension

import os
import platform
import subprocess

def set_libclang_path(libclang_path):
    if platform.system() == "Windows":
        os.environ["LIBCLANG_PATH"] = libclang_path
    else:
        outcome = subprocess.run(["export", f"LIBCLANG_PATH={libclang_path}"], shell=True)
        outcome.wait()

def install_libclang_mac():
    outcome = subprocess.run(["brew", "install", "llvm"], shell=True)
    outcome.wait()

def install_libclang_linux():
    distro = platform.linux_distribution()[0].lower()
    if distro in ["ubuntu", "debian"]:
        outcome = subprocess.run(["sudo", "apt-get", "install", "libclang-dev"], shell=True)
        outcome.wait()
    elif distro == "fedora":
        outcome = subprocess.run(["sudo", "dnf", "install", "libclang-devel"], shell=True)
        outcome.wait()
    elif distro == "arch":
        outcome = subprocess.run(["sudo", "pacman", "-S", "clang"], shell=True)
        outcome.wait()
    else:
        print("Unsupported Linux distribution. Please install libclang manually.")

def solve_libclang_error():
    libclang_path = ""
    
    if platform.system() == "Darwin":
        try:
            libclang_path = subprocess.check_output(["brew", "--prefix", "llvm"], shell=True).decode().strip() + "/lib/libclang.dylib"
        except subprocess.CalledProcessError:
            install_libclang_mac()
            libclang_path = "/usr/local/opt/llvm/lib/libclang.dylib"
    elif platform.system() == "Windows":
        try:
            libclang_path = subprocess.check_output(["where", "libclang.dll"]).decode().strip()
        except subprocess.CalledProcessError:
            print("Libclang not found. Please install LLVM and set LIBCLANG_PATH manually.")
    elif platform.system() == "Linux":
        try:
            libclang_path = subprocess.check_output(["find", "/usr", "-name", "libclang.so"]).decode().strip()
        except subprocess.CalledProcessError:
            install_libclang_linux()
            libclang_path = "/usr/lib/libclang.so"
    else:
        print("Unsupported operating system.")
    
    if libclang_path:
        set_libclang_path(libclang_path)
        print("LIBCLANG_PATH environment variable set successfully.")

# Run the script to solve the libclang error
solve_libclang_error()



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