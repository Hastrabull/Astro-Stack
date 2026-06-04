# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None

# Package metadata needed by astropy/photutils at runtime
datas = []
for pkg in ('photutils', 'astropy', 'numpy', 'scipy', 'rawpy', 'tetra3'):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Collect all of photutils and tetra3 (hooks may miss submodules)
photutils_datas, photutils_binaries, photutils_hiddenimports = collect_all('photutils')
tetra3_datas,    tetra3_binaries,    tetra3_hiddenimports    = collect_all('tetra3')

datas     += photutils_datas    + tetra3_datas
binaries   = photutils_binaries + tetra3_binaries
hiddenimports = (
    photutils_hiddenimports + tetra3_hiddenimports + [
        'astropy',
        'astropy.io.fits',
        'astropy.stats',
        'astropy.stats.sigma_clipping',
        'photutils',
        'photutils.detection',
        'photutils.detection.iraf_star_finder',
        'photutils.background',
        'rawpy',
        'scipy.interpolate',
        'scipy.stats',
        'tifffile',
        'PIL',
        'PIL.Image',
        'matplotlib',
        'matplotlib.backends.backend_qtagg',
        'tetra3',
        'tetra3.tetra3',
    ]
)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AstroStack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
