# Third-party notices

- **PyInstaller 6.22.3** is an optional build-time tool. Its GPLv2 license includes an exception permitting generated executables to be distributed under the application's license, subject to dependency licenses. No PyInstaller Python package is needed at runtime. [License and exception](https://pyinstaller.org/en/stable/license.html)
- **ngspice 47** is optional and runs as a separate executable. The ngspice source is primarily under a modified BSD license, with separately licensed components; retain the upstream notices when redistributing its official binary. CircuitStudio does not statically link ngspice. [Official download and Windows installation](https://ngspice.sourceforge.io/download.html), [manual license chapter](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf)
- **KiCad** is not bundled. The user supplies the separately installed KiCad application, symbol/footprint libraries, and bundled `pcbnew` runtime.
- **Python/Tcl/Tk** runtime files are bundled by PyInstaller. Their upstream license and notices are included in the selected Python distribution; this project does not modify those runtimes.
