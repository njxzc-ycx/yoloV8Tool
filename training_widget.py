import os
import shutil
import sys
import time
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QWidget, QLineEdit, QComboBox, QPushButton, QCheckBox, QLabel, QGroupBox, QTextEdit, \
    QVBoxLayout, QHBoxLayout, QGridLayout, QMessageBox, QFileDialog
from PyQt5 import uic
from shutil import copyfile
from TrainingThread import TrainingThread

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ui_file = resource_path("UI/training.ui")

trainingUi, trainingBase = uic.loadUiType(ui_file)


class TrainingWidget(QWidget, trainingUi):
    def __init__(self, parent=None):
        super(TrainingWidget, self).__init__(parent)
        self.setupUi(self)
        self.is_training = False

        self.current_project_dir = ''


        self.init_project_combobox()
        self.init_comboBox_model_weight()
        self.init_saved_model_combobox()

        self.label_batch.setToolTip("显存越小调越小 2,4,8,16,32,64 显存不够可减小，但会出现Nan问题(解决办法:增大batch)。")
        self.label_weight_decay.setToolTip("用于防止过拟合的一种正则化技术。典型值为 0.0005 或 0.0001。")
        self.label_width.setToolTip("32的倍数，否则不能加载网络，该值越大，识别效果越好。")
        self.label_height.setToolTip("32的倍数，否则不能加载网络，该值越大，识别效果越好。")
        self.label_epoch.setToolTip("训练次数上限。")
        self.label_learning_rate.setToolTip("太大会使结果超过最优值，太小会使loss值下降速度过慢。")
        self.label_momentum.setToolTip("动量是用于加速 SGD 优化的参数，通常在 0.9 左右。典型值为 0.9 到 0.95。")
        self.label_pretrained.setToolTip("如果设置为 True，将加载预训练模型的权重。可以加快训练速度并提高性能。")
        self.label_augment.setToolTip("如果设置为 True，则使用数据增强技术来扩充数据集。数据增强可以提高模型的泛化能力。")

        self.comboBox_model_weight.setToolTip("选择模型的初始权重文件。")

        self.btn_start_training.clicked.connect(self.start_training)
        self.btn_continue_training.clicked.connect(self.continue_training)
        self.btn_project_selection.clicked.connect(self.confirm_project_selection)
        self.btn_extract_model.clicked.connect(self.extract_model)
        self.btn_clear_runs.clicked.connect(self.clear_runs_folder)

    def init_project_combobox(self):
        settings = QSettings("MyCompany", "AnnotationTool")  # 使用 QSettings 记住用户的选择
        last_project = settings.value("last_train_project", "")
        if last_project != "":
            self.current_project_dir = os.path.join("Projects", last_project)
            self.datasets_dir = os.path.join(self.current_project_dir, "trans")
            self.lineEdit_datasets_folder.setText(self.datasets_dir)

            try:
                datasets_dir = os.listdir(self.datasets_dir)
            except FileNotFoundError:
                QMessageBox.warning(self, "错误", "数据文件夹不存在。请检查项目结构或重新创建项目。", QMessageBox.Ok)

                settings = QSettings("MyCompany", "AnnotationTool")
                settings.remove("last_train_project")

                self.comboBox_projectName.setCurrentIndex(-1)
                self.comboBox_projectName.clearEditText()
                self.comboBox_projectName.setEditText("")

                self.lineEdit_datasets_folder.setText("")

                return

        self.comboBox_projectName.clear()
        if os.path.exists("Projects"):
            project_names = os.listdir("Projects")
            self.comboBox_projectName.addItems([""])
            self.comboBox_projectName.addItems(project_names)  # 添加项目名称

        if last_project in project_names:
            self.comboBox_projectName.setCurrentText(last_project)

    def init_saved_model_combobox(self):
        if self.current_project_dir:
            saved_model_dir = os.path.join(self.current_project_dir, "savedModels")

            try:
                model_names = os.listdir(saved_model_dir)
            except FileNotFoundError:
                self.comboBox_select_weights.clear()
                self.comboBox_select_weights.setCurrentIndex(-1)
                self.comboBox_select_weights.clearEditText()
                self.comboBox_select_weights.setEditText("")
                QMessageBox.warning(self, "提示", "当前项目的模型文件夹不存在，请检查项目结构或重新创建项目。",
                                    QMessageBox.Ok)
                return

            if model_names:
                self.comboBox_select_weights.clear()
                self.comboBox_select_weights.addItems(["请选择模型"])
                self.comboBox_select_weights.addItems(model_names)
                self.comboBox_select_weights.setCurrentIndex(0)
            else:
                self.comboBox_select_weights.clear()
                self.comboBox_select_weights.addItems(["没有可用的模型"])
                self.comboBox_select_weights.setCurrentIndex(0)

    def store_selected_project(self):
        """存储当前选择的项目名称。"""
        current_project = self.comboBox_projectName.currentText()
        settings = QSettings("MyCompany", "AnnotationTool")
        settings.setValue("last_train_project", current_project)
        print(f"当前选择的项目已存储: {current_project}")

    def confirm_project_selection(self):
        selected_project = self.comboBox_projectName.currentText()
        if selected_project:
            self.init_saved_model_combobox()
            self.store_selected_project()
            self.current_project_dir = os.path.join(r"Projects", selected_project)
            self.datasets_dir = os.path.join(self.current_project_dir, "trans")
            self.lineEdit_datasets_folder.setText(self.datasets_dir)
        else:
            self.lineEdit_datasets_folder.setText("")
            self.comboBox_select_weights.clear()
            self.comboBox_select_weights.addItems(["没有可用的模型"])
            self.comboBox_select_weights.setCurrentIndex(0)

    def init_comboBox_model_weight(self):
        """初始化权重选择下拉框，查找ModelV8目录下的文件并显示到下拉框中"""
        model_dir = "./ModelV8"

        # 确保目录存在
        if not os.path.exists(model_dir):
            QMessageBox.warning(self, "错误", f"目录 {model_dir} 不存在。", QMessageBox.Ok)
            return

        # 获取ModelV8目录下的所有文件
        model_files = os.listdir(model_dir)

        weight_files = [f for f in model_files if os.path.isfile(os.path.join(model_dir, f)) and f.endswith('.pt')]

        # 清空下拉框并添加文件名
        self.comboBox_model_weight.clear()
        self.comboBox_model_weight.addItems(weight_files)

        if weight_files:
            self.comboBox_model_weight.insertItem(0, "请选择模型")
            self.comboBox_model_weight.setCurrentIndex(0)
        else:
            self.comboBox_model_weight.addItem("没有可用的模型")

    def start_training(self):
        if self.comboBox_model_weight.currentIndex() == 0:
            QMessageBox.information(self, "提示", "请选择训练的参照模型", QMessageBox.Ok)
            return

        if self.is_training:
            QMessageBox.information(self, "提示", "已经正在训练模型....", QMessageBox.Ok)
            return
        else:
            self.is_training = True

        batch_size = self.lineEdit_batch.text()
        width = self.lineEdit_width.text()
        epoch = self.lineEdit_epoch.text()
        learning_rate = self.lineEdit_learning_rate.text()

        config = {
            'batch_size': batch_size,
            'imgsz': width,
            'epoch': epoch,
            'learning_rate': learning_rate,
            'weights': sys.path[0] + "/ModelV8/" + self.comboBox_model_weight.currentText(),
            'datasets': sys.path[0] + "/" + self.lineEdit_datasets_folder.text(),
            'weight_decay': float(self.lineEdit_weight_decay.text()),
            'momentum': float(self.lineEdit_momentum.text()),
            'pretrained': self.checkBox_pretrained.isChecked(),
            'augment': self.checkBox_augment.isChecked()
        }

        print("训练配置:", config)


        self.thread = TrainingThread(config)
        self.thread.trainingStarted.connect(self.on_training_started)
        self.thread.trainingFinished.connect(self.on_training_finished)
        self.thread.trainingError.connect(self.on_training_error)
        self.thread.trainingOutput.connect(self.on_training_output)
        self.thread.start()

    def continue_training(self):
        if self.comboBox_select_weights.currentIndex() == 0:
            QMessageBox.information(self, "提示", "请选择继续训练的权重模型", QMessageBox.Ok)
            return

        if self.is_training:
            QMessageBox.information(self, "提示", "已经正在训练模型....", QMessageBox.Ok)
            return
        else:
            self.is_training = True

        batch_size = self.lineEdit_batch.text()
        width = self.lineEdit_width.text()
        epoch = self.lineEdit_epoch.text()
        learning_rate = self.lineEdit_learning_rate.text()

        config = {
            'batch_size': batch_size,
            'imgsz': width,
            'epoch': epoch,
            'learning_rate': learning_rate,
            'weights': sys.path[0] + "/" + self.current_project_dir + "/savedModels/" + self.comboBox_select_weights.currentText(),
            'datasets': sys.path[0] + "/" + self.lineEdit_datasets_folder.text(),
            'weight_decay': float(self.lineEdit_weight_decay.text()),
            'momentum': float(self.lineEdit_momentum.text()),
            'pretrained': self.checkBox_pretrained.isChecked(),
            'augment': self.checkBox_augment.isChecked()
        }

        print("训练配置:", config)


        self.thread = TrainingThread(config)
        self.thread.trainingStarted.connect(self.on_training_started)
        self.thread.trainingFinished.connect(self.on_training_finished)
        self.thread.trainingError.connect(self.on_training_error)
        self.thread.trainingOutput.connect(self.on_training_output)
        self.thread.start()

    def on_training_output(self, output):
        self.textEdit_training_log.append(output)

    def on_training_finished(self, best_model_path,last_model_path):
        QMessageBox.information(self, "训练完成", "训练已经完成。", QMessageBox.Ok)

        self.is_training = False

        if best_model_path and os.path.exists(best_model_path) and last_model_path and os.path.exists(last_model_path):
            target_dir = os.path.join(self.current_project_dir, "savedModels")
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            best_model_filename = os.path.basename(best_model_path)
            best_target_path = os.path.join(target_dir, best_model_filename)
            last_model_filename = os.path.basename(last_model_path)
            last_target_path = os.path.join(target_dir, last_model_filename)

            try:
                copyfile(best_model_path, best_target_path)
                copyfile(last_model_path, last_target_path)
                self.init_saved_model_combobox()
                QMessageBox.information(self, "模型保存成功", f"最优模型已保存到: {best_target_path}, 最新模型已保存到: {last_target_path}", QMessageBox.Ok)
            except Exception as e:
                QMessageBox.critical(self, "文件保存错误", f"无法保存模型文件:\n{str(e)}", QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "训练结果错误", "未能获取训练完成的模型路径。", QMessageBox.Ok)

    def on_training_started(self):
        QMessageBox.information(self, "训练开始", "训练已经开始，请等待训练完成。", QMessageBox.Ok)

    def on_training_error(self, error_message):
        QMessageBox.critical(self, "训练错误", f"训练过程中发生错误:\n{error_message}", QMessageBox.Ok)

    def extract_model(self):
        if self.comboBox_select_weights.currentIndex() == 0:
            QMessageBox.information(self, "提示", "请选择需要提取的权重模型", QMessageBox.Ok)
            return

        selected_model = sys.path[0] + "/" + self.current_project_dir + "/savedModels/" + self.comboBox_select_weights.currentText()

        save_path, _ = QFileDialog.getSaveFileName(self, "保存模型", selected_model, "Model Files (*.pt *.h5 *.onnx)")

        if save_path:
            try:
                shutil.copy(selected_model, save_path)
                QMessageBox.information(self, "成功", f"模型已保存到: {save_path}", QMessageBox.Ok)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存模型时出现错误: {str(e)}", QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "提示", "未选择保存地址", QMessageBox.Ok)

    def clear_runs_folder(self):
        if self.is_training:
            QMessageBox.information(self, "提示", "正在训练模型，禁止删除！", QMessageBox.Ok)
            return

        reply = QMessageBox.question(self, '确认', '确定要清空runs文件夹吗？此操作不可撤销！',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            runs_folder_path = 'runs'
            if os.path.exists(runs_folder_path):
                shutil.rmtree(runs_folder_path)
                os.makedirs(runs_folder_path)
                QMessageBox.information(self, "提示", "runs文件夹已清空！")
            else:
                QMessageBox.warning(self, "警告", "runs文件夹不存在！")
        else:
            QMessageBox.information(self, "提示", "操作已取消。")