#!/usr/bin/env python3

import sys
import argparse
import os
import os.path
import platform
import time
import subprocess
import shutil
import re
import matplotlib.pyplot as plt
import collections
from pathlib import Path
from functools import reduce

plt.style.use('ggplot')
width = 0.15
colors = {'mkl': 'red',
          'mlir': 'dodgerblue',
          'openblas': 'mediumseagreen',
          'halide': 'gold',
          'ruy': 'violet'}

def add_arguments(parser):
    parser.add_argument('bins', type=Path, help='Path where the test binaries are')
    parser.add_argument('results', type=Path, help='Result directory')

def main(argv):
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args(argv[1:])

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    #result_dir = os.path.abspath(os.path.join(args.results, timestamp))
    result_dir = (args.results / timestamp).resolve()
    os.makedirs(result_dir)

    pfm = platform.system()

    if pfm == "Linux":
        # linux
        print("Linux System Detected.. looking for /proc/cpuinfo")
        shutil.copyfile(Path("/proc/cpuinfo"), result_dir / "cpuinfo")

        cpu_pattern = re.compile('cpu[0-9]+')
        cpudirs = [x for x in Path("/sys/devices/system/cpu/").iterdir() if cpu_pattern.match(x.name)]
        with open(result_dir / 'scaling_governor', 'w') as f:
            for cpu in cpudirs:
                f.write(cpu.name + ": " + (cpu / 'cpufreq' / 'scaling_governor').read_text())
        cpudirs = [x for x in Path("/sys/devices/system/cpu/").iterdir() if cpu_pattern.match(x.name)]
        with open(result_dir / 'core_frequencies', 'w') as f:
            for cpu in cpudirs:
                f.write(cpu.name + ": " + (cpu / 'cpufreq' / 'scaling_cur_freq').read_text())
    elif pfm == "Darwin":
        # OSX
        print("OSX System Detected")
    else:
        print("Unidentified system")

    with open(result_dir / 'arch-info', 'w') as fh:
        proc = subprocess.run([args.bins.parent / "cpuinfo-install" / "bin" / "cpu-info"],
                              capture_output=True, text=True, check=True)
        fh.write(proc.stdout)
        proc = subprocess.run([args.bins.parent / "cpuinfo-install" / "bin" / "isa-info"],
                              capture_output=True, text=True, check=True)
        fh.write(proc.stdout)
        proc = subprocess.run([args.bins.parent / "cpuinfo-install" / "bin" / "cache-info"],
                              capture_output=True, text=True, check=True)
        fh.write(proc.stdout)

    # get only the executables
    bin_paths = [x for x in args.bins.iterdir() if
                x.is_file() and x.stat().st_mode & 0o111 and x.name.startswith('matmul')]
    # break up and interpret the file names
    binaries = {}
    for path in bin_paths:
        parts = path.name.split('_')[1:]
        size = tuple(int(y) for y in parts[1].split('x'))
        binaries.setdefault(parts[0], []).append(
            {'path': path.resolve(), 'size': size})

    my_env = os.environ.copy()
    my_env["MKL_NUM_THREADS"] = "1"
    my_env["OPENBLAS_NUM_THREADS"] = "1"
    my_env["HL_NUM_THREADS"] = "1"
    my_env["THREADS"] = "1"

    # used to impose a consistent sorting of the matrix sizes in the plot
    bar_ordering = list(collections.OrderedDict.fromkeys(y['size'] for x in binaries for y in binaries[x]))
    bar_ordering.sort(key=lambda s: (reduce(lambda x, y: x*y, s), s))

    for idx, backend in enumerate(binaries):
        bar_x = []
        speeds = []
        for binary in binaries[backend]:
            print(backend, binary)
            subprocess.run([binary['path']], cwd=result_dir, env=my_env, check=True)
            speeds.append(float((result_dir / (binary['path'].name + '_perf.out')).read_text().split()[0]))
            bar_x.append(bar_ordering.index(binary['size']) + idx * width)
        plt.bar(bar_x, speeds, width, color=colors[backend], label=backend)

    plt.xlabel("Matrix sizes")
    plt.ylabel("GFLOPS")
    plt.title("Single Precision Matrix Multiplication")
    x_pos = [i + 0.5*(len(binaries) - 1)*width for i in range(len(bar_ordering))]
    plt.xticks(x_pos, ['x'.join(str(d) for d in s) for s in bar_ordering], rotation=90, fontsize=5)
    plt.legend(loc='best')
    plt.savefig(result_dir / 'matmul.png', dpi=300, bbox_inches='tight')


    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))