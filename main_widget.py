import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QSizePolicy
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from annotation_widget import AnnotationWidget
from training_widget import TrainingWidget
from validation_widget import ValidationWidget


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ui_file = resource_path("UI/main.ui")

# 主界面UI配置文件
mainUi, mainBase = uic.loadUiType(ui_file)

class MainWidget(QMainWindow, mainUi):
    def __init__(self):
        super(MainWidget, self).__init__()
        self.setupUi(self)


        self.tabWidget.clear()


        self.annotation_tab = AnnotationWidget()
        self.training_tab = TrainingWidget()
        self.validation_tab  = ValidationWidget()


        self.tabWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabWidget.setMinimumSize(800, 600)


        self.tabWidget.addTab(self.annotation_tab, "标注")
        self.tabWidget.addTab(self.training_tab, "训练")
        self.tabWidget.addTab(self.validation_tab, "验证模型")

        self.setWindowIcon(QIcon("./Images/logo.png"))
        self.setWindowTitle("YoloV8Tool")


        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1000, 700)

    def resizeEvent(self, event):

        self.tabWidget.setGeometry(self.rect())
        super(MainWidget, self).resizeEvent(event)

if __name__ == "__main__":
    cApp = QApplication(sys.argv)
    cMainWidget = MainWidget()
    cMainWidget.show()
    sys.exit(cApp.exec_())
