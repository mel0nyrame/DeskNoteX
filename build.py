import PyInstaller.__main__
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
main_script = os.path.join(here, "main.py")

args = [
    main_script,
    "--name=DeskNoteX",
    "--onefile",
    "--windowed",
    "--noconsole",
    # Exclude heavy Qt modules to reduce size
    "--exclude-module=PyQt5.QtWebEngine",
    "--exclude-module=PyQt5.QtWebEngineCore",
    "--exclude-module=PyQt5.QtWebEngineWidgets",
    "--exclude-module=PyQt5.QtWebKit",
    "--exclude-module=PyQt5.QtWebKitWidgets",
    "--exclude-module=PyQt5.Qt3D",
    "--exclude-module=PyQt5.Qt3DRender",
    "--exclude-module=PyQt5.Qt3DInput",
    "--exclude-module=PyQt5.Qt3DLogic",
    "--exclude-module=PyQt5.Qt3DExtras",
    "--exclude-module=PyQt5.QtMultimedia",
    "--exclude-module=PyQt5.QtMultimediaWidgets",
    "--exclude-module=PyQt5.QtBluetooth",
    "--exclude-module=PyQt5.QtLocation",
    "--exclude-module=PyQt5.QtPositioning",
    "--exclude-module=PyQt5.QtSensors",
    "--exclude-module=PyQt5.QtSerialPort",
    "--exclude-module=PyQt5.QtSql",
    "--exclude-module=PyQt5.QtTest",
    "--exclude-module=PyQt5.QtXml",
    "--exclude-module=PyQt5.QtXmlPatterns",
    "--exclude-module=PyQt5.QtNetwork",
    "--exclude-module=PyQt5.QtDesigner",
    "--exclude-module=PyQt5.QtHelp",
    "--exclude-module=PyQt5.QtOpenGL",
    "--exclude-module=PyQt5.QtPrintSupport",
    "--exclude-module=PyQt5.QtSvg",
    "--exclude-module=PyQt5.QtCharts",
    "--exclude-module=PyQt5.QtDataVisualization",
    "--exclude-module=PyQt5.QtQuick",
    "--exclude-module=PyQt5.QtQuickWidgets",
    "--exclude-module=PyQt5.QtQml",
    "--exclude-module=PyQt5.QtNfc",
    # Data
    "--add-data=assets;assets",
    "--icon=assets/icon.ico",
    # Output
    "--distpath=dist",
    "--workpath=build",
    "--specpath=.",
    # Icon
    "--icon=assets/icon.ico",
]

PyInstaller.__main__.run(args)