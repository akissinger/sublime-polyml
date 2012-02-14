Poly/ML Package for Sublime Text 2
==================================

This package adds syntax highlighting and build system support for Poly/ML source files. It works best when used in conjunction with the [isaplib][isaplib] Poly/ML library, which adds support for incremental building of source files via PolyML.Project.

[isplib]: https://github.com/Quantomatic/isaplib


Installing
----------

The package can be installed by running the following commands:

    cd $PACKAGE_DIR
    git clone git://github.com/akissinger/sublime-polyml.git PolyML
    
Done! On OS X, `PACKAGE_DIR` is `~/Library/Application Support/Sublime Text 2/Packages/`. PolyML should show up as an option under Build Systems, and `.ML` files should highlight correctly.

The package provides the command 'run_poly', which can be bound to a hotkey, called from another plugin, etc.

Configuration
-------------

At some point, I'll add some smarts so that the package can find Poly/ML on most systems. In the mean time, add the following line to your `Base File.sublime-settings`:

    "poly_bin": "/usr/local/bin/poly"

Where `"/usr/local/bin/poly"` is pointing to where your `poly` executable is installed.
