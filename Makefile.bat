cd ui
pyuic4 -o ui_aboutdialogbase.py aboutdialogbase.ui
pyuic4 -o ui_qtilesdialogbase.py qtilesdialogbase.ui
cd ..
pyrcc4 -o resources_rc.py resources.qrc
lrelease i18n\qtiles_ru.ts
cd ..
zip -r qtiles.zip qtiles -x \*.pyc \*.ts \*.ui \*.qrc \*.pro \*~ \*.git\* \*.svn\* \*Makefile*