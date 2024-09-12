import subprocess
import sys

from PyQt5.QtWidgets import QCheckBox, QMenu, QAction
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
    QProgressDialog, QTableWidgetItem, QTableWidget, QProgressBar, QSizePolicy, QInputDialog
)
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
import os
import shutil
import threading
from image_widget import CImageWidget
from to_coco import COCOCreater
import math

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ui_file = resource_path("UI/annotation.ui")

# 标注界面UI配置文件
annotationUi, annotationBase = uic.loadUiType(ui_file)

class AnnotationWidget(QWidget, annotationUi):
    trans_signal = pyqtSignal(int)  # 定义一个信号，用于转换进度

    def __init__(self, parent=None):
        super(AnnotationWidget, self).__init__(parent)
        self.setupUi(self)

        # 初始化变量
        self.image_dir = ''
        self.label_file = ''
        self.coco_dir = ''
        self.current_project_dir = ''
        self.saved_models_dir = ''
        self.label_info = {}
        self.image_widgets = []  # 用于存储所有图像控件
        self.categories = []  # 初始化类别列表
        self.batch_index = 0  # 批次索引
        self.total_batch = 0  # 批次索引
        self.side = 1
        self.total = 1
        self.trans_process = None
        self.trans_dialog = None
        self.tableWidget_labels.verticalHeader().setVisible(False)
        self.tableWidget_labels.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableWidget_labels.customContextMenuRequested.connect(self.show_context_menu)

        # 设置 UI 布局
        self.setup_layout()

        # 连接信号和槽
        self.trans_signal.connect(self.trans_slot)
        self.btn_open.clicked.connect(self.slot_btn_open)
        self.btn_refresh.clicked.connect(self.refresh_labels)
        self.btn_skip_to_unlabeled.clicked.connect(self.skip_to_unlabeled)
        self.btn_clear.clicked.connect(self.clear_project)
        self.btn_back.clicked.connect(self.slot_btn_pre)
        self.btn_save.clicked.connect(self.slot_btn_save)
        self.btn_next.clicked.connect(self.slot_btn_next)
        self.btn_createProject.clicked.connect(self.create_project)  # 创建项目按钮连接槽函数
        self.btn_addLabel.clicked.connect(self.add_category)  # 连接添加类别按钮
        self.btn_toCoCo.clicked.connect(self.slot_btn_to_coco)

        # 初始化按钮状态
        self.update_data_info(0, 0, 0, 0)  # 示例初始化数据

        # 初始化项目名称下拉框
        self.init_project_combobox()

        # 连接 QComboBox 的 currentIndexChanged 信号到槽函数
        self.comboBox_projectName.currentIndexChanged.connect(self.on_project_selected)
        self.on_project_selected()

    def setup_layout(self):
        """设置图像展示的布局。"""
        # 使用 QVBoxLayout 布局
        left_layout = self.findChild(QVBoxLayout, 'leftLayout')
        hbox = QHBoxLayout()

        # 创建用于显示图像的控件
        for i in range(self.total):
            image_widget = CImageWidget()
            image_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置大小策略
            self.image_widgets.append(image_widget)
            hbox.addWidget(image_widget)

        left_layout.addLayout(hbox)

    def init_project_combobox(self):
        """初始化项目名称下拉框，列出已有的项目，并记住上一次的选项。"""
        settings = QSettings("MyCompany", "AnnotationTool")  # 使用 QSettings 记住用户的选择
        last_project = settings.value("last_project", "")  # 读取上一次的选择，默认为空
        if last_project != "":
            project_dir = os.path.join("Projects", last_project)
            self.image_dir = os.path.join(project_dir, "data")
            self.label_file = os.path.join(project_dir, "label.txt")

            # 初始化批次索引为第一页
            self.batch_index = 0

            # 加载标签文件和图片
            self.read_label_file()  # 读取标签文件

            try:
                image_files = os.listdir(self.image_dir)
            except FileNotFoundError:
                QMessageBox.warning(self, "错误", "数据文件夹不存在。请检查项目结构或重新创建项目。", QMessageBox.Ok)

                # 清除 QSettings 中存储的上次选择的项目名称
                settings = QSettings("MyCompany", "AnnotationTool")
                settings.remove("last_project")  # 移除 last_project 项

                # 清除上次选择的项目名称并重置下拉框
                self.comboBox_projectName.setCurrentIndex(-1)  # 清空选择
                self.comboBox_projectName.clearEditText()  # 清除文本编辑框
                self.comboBox_projectName.setEditText("")  # 设置空文本

                # 清空控件中显示的图像信息
                for image_widget in self.image_widgets:
                    image_widget.set_info(None, None)

                return  # 退出函数，不执行后续代码
            # 加载第一页的图片
            image_names = list(self.label_info.keys())[0:self.total]
            if image_names:
                for i in range(self.total):
                    if i < len(image_names):
                        img_path = os.path.join(self.image_dir, image_names[i])
                        self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                        # if i == 0:  # 更新显示第一个图像的名称
                        #     self.update_image_label(image_names[i])

            # 更新数据标签显示
            self.update_data_info(len(image_files), 0, len(image_files), 0)
            self.progressBar.setValue(0)

        self.comboBox_projectName.clear()
        if os.path.exists("Projects"):
            project_names = os.listdir("Projects")
            self.comboBox_projectName.addItems([""])
            self.comboBox_projectName.addItems(project_names)  # 添加项目名称

        # 如果上次选择的项目存在，则设置为当前选中项
        if last_project in project_names:
            self.comboBox_projectName.setCurrentText(last_project)

    def create_project(self):
        """创建新项目的槽函数。"""
        # 弹出输入对话框，获取项目名称
        project_name, ok = QInputDialog.getText(self, "新建项目", "请输入项目名称:")
        if ok and project_name:  # 点击确认且输入不为空
            project_dir = os.path.join("Projects", project_name)
            if not os.path.exists("Projects"):
                os.makedirs("Projects")  # 如果 Projects 目录不存在，则创建
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)  # 创建新项目文件夹
                os.makedirs(os.path.join(project_dir, "data"))
                os.makedirs(os.path.join(project_dir, "trans"))
                os.makedirs(os.path.join(project_dir, "savedModels"))
                label_file_path = os.path.join(project_dir, "label.txt")
                with open(label_file_path, 'w') as f:
                    f.write("")  # 创建一个空的 label.txt 文件
                QMessageBox.information(self, "提示", f"项目 {project_name} 创建成功。", QMessageBox.Yes)
                # 更新下拉框，添加新项目名称
                self.comboBox_projectName.addItem(project_name)
                self.comboBox_projectName.setCurrentText(project_name)  # 设置当前选择为新创建的项目
                self.store_selected_project()


            else:
                QMessageBox.warning(self, "警告", f"项目 {project_name} 已经存在。", QMessageBox.Ok)
        elif not project_name:
            QMessageBox.warning(self, "警告", "项目名称不能为空。", QMessageBox.Ok)

    def store_selected_project(self):
        """存储当前选择的项目名称。"""
        current_project = self.comboBox_projectName.currentText()
        settings = QSettings("MyCompany", "AnnotationTool")
        settings.setValue("last_project", current_project)
        print(f"当前选择的项目已存储: {current_project}")

    def on_project_selected(self):
        """当选择项目时加载项目的图片、标签和类别。"""
        selected_project = self.comboBox_projectName.currentText()
        if selected_project:
            self.store_selected_project()
            self.current_project_dir = os.path.join("Projects", selected_project)
            self.image_dir = os.path.join(self.current_project_dir, "data")
            self.label_file = os.path.join(self.current_project_dir, "label.txt")
            self.coco_dir = os.path.join(self.current_project_dir, "trans")
            self.saved_models_dir = os.path.join(self.current_project_dir, "savedModels")

            # 初始化批次索引为第一页
            self.batch_index = 0

            # 加载标签文件和图片
            self.read_label_file()  # 读取标签文件
            self.load_categories()  # 加载类别列表
            image_files = os.listdir(self.image_dir)

            # 加载第一页的图片
            image_names = list(self.label_info.keys())[0:self.total]
            if image_names:
                for i in range(self.total):
                    if i < len(image_names):
                        img_path = os.path.join(self.image_dir, image_names[i])
                        self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                        # if i == 0:  # 更新显示第一个图像的名称
                        #     self.update_image_label(image_names[i])

            # 更新数据标签显示
            self.update_data_info(len(image_files), 1, len(image_files), 0)
            self.progressBar.setValue(0)

    def slot_btn_open(self):
        """打开图库按钮的槽函数，直接打开项目的 data 文件夹。"""
        current_project = self.comboBox_projectName.currentText()
        if current_project:  # 确保有一个选中的项目
            project_dir = os.path.join("Projects", current_project)
            data_dir = os.path.join(project_dir, "data")
            if os.path.exists(data_dir):
                subprocess.Popen(f'explorer "{os.path.abspath(data_dir)}"')  # 打开 data 文件夹的资源管理器
            else:
                QMessageBox.warning(self, "警告", "data 文件夹不存在。", QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "警告", "请先选择一个项目。", QMessageBox.Ok)

    def update_data_info(self, total, current, total_shown, progress):
        """更新数据标签显示。"""
        self.label_dataInfo.setText(f"( 共{total}张，现{current}/{total_shown}张，进度{progress}% )")
        self.label_dataInfo.setStyleSheet("color: blue;")  # 设置文本颜色

    # def update_image_label(self, image_name):
    #     """更新图像名称标签的文本。"""
    #     self.imageLabel.setText(f"当前图名：{image_name}")  # 动态更新图像名称显示

    def refresh_labels(self):
        selected_project = self.comboBox_projectName.currentText()
        if selected_project:  # 如果选择了一个有效的项目
            project_dir = os.path.join("Projects", selected_project)
            self.image_dir = os.path.join(project_dir, "data")
            self.label_file = os.path.join(project_dir, "label.txt")

            # 初始化批次索引为第一页
            self.batch_index = 0

            # 加载标签文件和图片
            self.read_label_file()  # 读取标签文件
            image_files = os.listdir(self.image_dir)

            # 加载第一页的图片
            image_names = list(self.label_info.keys())[0:self.total]
            if image_names:
                for i in range(self.total):
                    if i < len(image_names):
                        img_path = os.path.join(self.image_dir, image_names[i])
                        self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                        # if i == 0:  # 更新显示第一个图像的名称
                        #     self.update_image_label(image_names[i])

            # 更新数据标签显示
            self.update_data_info(len(image_files), 0, len(image_files), 0)
            self.progressBar.setValue(0)

    def skip_to_unlabeled(self):
        """跳转到未标记的图片。"""
        for index, (image_name, boxes) in enumerate(self.label_info.items()):
            if not boxes:  # 如果没有标注
                self.batch_index = index // self.total  # 计算批次索引
                self.save_box_info()  # 保存当前图像的标注信息
                self.write_label_file()  # 将标注信息写入文件
                self.display_images()  # 显示未标记的图片

                # 更新右侧状态栏的信息
                current_batch = self.batch_index + 1
                self.update_data_info(
                    total=len(self.label_info),
                    current=current_batch,
                    total_shown=self.total_batch,
                    progress=int((self.batch_index / (self.total_batch - 1)) * 100 if self.total_batch > 1 else 100)
                )
                return

        # 如果没有找到未标记的图片，弹出信息提示
        QMessageBox.information(self, "提示", "所有图片都已标记。", QMessageBox.Ok)

    def display_images(self):
        """根据当前批次索引显示图片。"""
        start_idx = self.batch_index * self.total
        end_idx = start_idx + self.total
        image_names = list(self.label_info.keys())[start_idx:end_idx]

        for i in range(self.total):
            if i < len(image_names):
                img_path = os.path.join(self.image_dir, image_names[i])
                self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                # if i == 0:  # 更新显示第一个图像的名称
                #     self.update_image_label(image_names[i])
            else:
                self.image_widgets[i].set_info(None, None)  # 清除没有图片的显示

        if self.total_batch > 0:
            current_batch = self.batch_index + 1
            self.update_data_info(len(self.label_info), current_batch, self.total_batch,
                                  int((self.batch_index / (
                                              self.total_batch - 1)) * 100 if self.total_batch > 1 else 100))
            self.progressBar.setValue(
                (self.batch_index / (self.total_batch - 1)) * 100 if self.total_batch > 1 else 100)
        else:
            self.update_data_info(len(self.label_info), 0, 0, 0)
            self.progressBar.setValue(0)

    def clear_project(self):
        """清除项目的槽函数。"""
        print("清除当前项目...")
        current_project = self.comboBox_projectName.currentText()

        if not current_project:
            QMessageBox.warning(self, "警告", "没有选择任何项目。", QMessageBox.Ok)
            return

        reply = QMessageBox.question(self, "确认",
                                     f"确定要清除当前项目 '{current_project}' 的所有数据吗？这将删除项目文件夹及其内容！",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            project_dir = os.path.join("Projects", current_project)

            # 删除项目文件夹及其内容
            if os.path.exists(project_dir):
                try:
                    shutil.rmtree(project_dir)
                    QMessageBox.information(self, "提示", f"项目 '{current_project}' 已删除。", QMessageBox.Yes)

                    # 从下拉框中删除项目名称
                    index = self.comboBox_projectName.findText(current_project)
                    if index != -1:
                        self.comboBox_projectName.removeItem(index)

                    # 清除界面上的所有状态
                    self.label_info.clear()
                    self.tableWidget_labels.setRowCount(0)
                    self.progressBar.setValue(0)
                    for image_widget in self.image_widgets:
                        image_widget.set_info(None, None)

                    # 清除QSettings中的上次选择的项目名称
                    settings = QSettings("MyCompany", "AnnotationTool")
                    settings.remove("last_project")

                    self.update_data_info(0, 0, 0, 0)
                    self.progressBar.setValue(0)

                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法删除项目文件夹：{str(e)}", QMessageBox.Ok)
            else:
                QMessageBox.warning(self, "警告", "项目文件夹不存在。", QMessageBox.Ok)

    def add_category(self):
        """添加新的类别到类别列表。"""
        category_name = self.lineEdit_labelName.text().strip()

        # 检查输入是否合法
        if not category_name:
            QMessageBox.warning(self, "警告", "类别名称不能为空。", QMessageBox.Ok)
            return
        if category_name in self.categories:
            QMessageBox.warning(self, "警告", "类别已经存在。", QMessageBox.Ok)
            return

        # 添加类别到列表
        self.categories.append((len(self.categories),category_name))
        self.lineEdit_labelName.clear()
        self.update_label_table()
        self.save_categories()

    def update_label_table(self):
        """更新标签列表表格显示。"""
        self.tableWidget_labels.setRowCount(0)
        for i, (category_id, category_name) in enumerate(self.categories):
            self.tableWidget_labels.insertRow(i)

            # 添加复选框项
            checkbox = QCheckBox()
            checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
            checkbox.stateChanged.connect(self.on_checkbox_state_changed)
            self.tableWidget_labels.setCellWidget(i, 0, checkbox)

            # 添加序号项，并设置为不可编辑
            item_id = QTableWidgetItem(str(category_id))
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tableWidget_labels.setItem(i, 1, item_id)

            # 添加类别名称项，并设置为不可编辑
            item_name = QTableWidgetItem(category_name)
            item_name.setTextAlignment(Qt.AlignCenter)
            item_name.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tableWidget_labels.setItem(i, 2, item_name)

    def save_categories(self):
        """将类别列表保存到当前项目目录中的 categories.txt 文件中。"""
        if not self.current_project_dir:
            return
        categories_file_path = os.path.join(self.current_project_dir, 'categories.txt')
        with open(categories_file_path, 'w') as f:
            for i, (category_id, category_name) in enumerate(self.categories):
                f.write(f'{category_id} {category_name}\n')

    def load_categories(self):
        """从项目文件中加载类别列表。"""
        self.categories = []  # 重置类别列表

        category_file_path = os.path.join(self.current_project_dir, "categories.txt")
        if os.path.exists(category_file_path):
            with open(category_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:

                        parts = line.split(' ', 1)
                        if len(parts) == 2:
                            category_id, category_name = parts
                            self.categories.append((int(category_id), category_name))
                        else:
                            print(f"Warning: Incorrect format in categories.txt: {line}")

        self.update_label_table()

    def on_checkbox_state_changed(self, state):
        """处理标签复选框的状态变化。"""
        # 获取复选框的父行
        sender = self.sender()
        row = self.tableWidget_labels.indexAt(sender.pos()).row()

        # 取消其他行的复选框选中状态
        for i in range(self.tableWidget_labels.rowCount()):
            checkbox = self.tableWidget_labels.cellWidget(i, 0)
            if checkbox and i != row:
                checkbox.setChecked(False)

        # 获取选中的标签名称
        if state == Qt.Checked:
            label_name = self.tableWidget_labels.item(row, 2).text()
            label_id = self.tableWidget_labels.item(row, 1).text()
            print(f"Selected label to annotate: {label_name}")

            # 遍历所有的图像控件，并设置当前类别
            for image_widget in self.image_widgets:
                image_widget.set_current_class(int(label_id))
        else:
            for image_widget in self.image_widgets:
                image_widget.set_current_class(-1)

    def trans_slot(self, trans_value):
        """处理转换进度信号的槽函数。"""
        print('get signal: ', trans_value)
        self.trans_dialog.setValue(trans_value)
        if trans_value == 100:
            QMessageBox.information(self, "提示", "转换结束", QMessageBox.Yes)

    def slot_btn_next(self):
        """下一张按钮的槽函数。"""
        self.save_box_info()
        self.write_label_file()


        image_names = self.update_batch_index(next=True, pre=False)

        if image_names is not None:
            for i in range(self.total):  # self.total 控制每次显示几张图片
                if i < len(image_names):
                    img_path = os.path.join(self.image_dir, image_names[i])
                    self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                    # if i == 0:  # 更新显示第一个图像的名称
                    #     self.update_image_label(image_names[i])
            # 更新数据标签显示
            self.update_data_info(len(self.label_info), self.batch_index + 1, self.total_batch,
                                  int((self.batch_index / (self.total_batch - 1)) * 100))
        else:  # 如果没有图片可显示
            QMessageBox.information(self, "提示", "已经是最后一张了。", QMessageBox.Ok)

    def slot_btn_pre(self):
        """上一张按钮的槽函数。"""
        self.save_box_info()  # 保存当前图像的标注信息
        self.write_label_file()  # 将标注信息写入文件

        # 更新批次索引，确保只在点击上一张时调用
        image_names = self.update_batch_index(next=False, pre=True)

        if image_names is not None:  # 如果有图片可显示
            for i in range(self.total):
                if i < len(image_names):
                    img_path = os.path.join(self.image_dir, image_names[i])
                    self.image_widgets[i].set_info(img_path, self.label_info[image_names[i]])
                    # if i == 0:  # 更新显示第一个图像的名称
                    #     self.update_image_label(image_names[i])
            # 更新数据标签显示
            self.update_data_info(len(self.label_info), self.batch_index + 1, self.total_batch,
                                  int((self.batch_index / (self.total_batch - 1)) * 100))
        else:  # 如果没有图片可显示
            QMessageBox.information(self, "提示", "已经是第一张了。", QMessageBox.Ok)

    def slot_btn_to_coco(self):
        """转换为 COCO 格式按钮的槽函数。"""
        self.slot_btn_save()
        if self.trans_process is not None and self.trans_process.is_alive():
            QMessageBox.critical(self, "提示", "正在转换数据集，请稍后", QMessageBox.Yes)
            return

        if self.coco_dir == "":
            QMessageBox.critical(self, "提示", "请选择项目", QMessageBox.Yes)


        save_dir = self.coco_dir
        if os.path.exists(save_dir):
            if os.listdir(save_dir):
                ret = QMessageBox.critical(self, "警告", f"文件夹({save_dir})非空，继续转换将会清空该文件夹", QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    shutil.rmtree(save_dir)
                    os.mkdir(save_dir)
                else:
                    return

            self.trans_process = threading.Thread(target=self.trans_data, args=(self.image_dir, save_dir, 'coco',))
            self.trans_process.start()

            self.trans_dialog = QProgressDialog(self)
            self.trans_dialog.setWindowTitle("转换中")
            self.trans_dialog.setLabelText("正在转换，请勿关闭...")
            self.trans_dialog.setMinimumDuration(1)
            self.trans_dialog.setWindowModality(Qt.WindowModal)
            self.trans_dialog.setRange(1, 100)
            self.trans_dialog.setValue(1)
            self.trans_dialog.show()

    def trans_data(self, src_dir, dst_dir, trans_type):
        """转换数据的逻辑。"""
        if trans_type == 'coco':
            coco = COCOCreater(src_dir, dst_dir)
            coco.read_ori_labels()
            self.trans_signal.emit(10)
            max_cls = coco.create_train_map()
            self.trans_signal.emit(60)
            coco.create_val_map()
            self.trans_signal.emit(70)
            coco.create_dataset_yaml()
            self.trans_signal.emit(100)
        else:
            print('unsupported type:', trans_type)

    def slot_btn_save(self):
        current_project = self.comboBox_projectName.currentText()
        if not current_project:
            QMessageBox.warning(self, "警告", "没有选择任何项目。", QMessageBox.Ok)
            return

        """保存按钮的槽函数。"""
        self.save_box_info()
        self.write_label_file()

    def read_label_file(self):
        """读取标签文件，并初始化所有图片的标签信息。"""
        # 确保标签字典是空的
        self.label_info.clear()

        # 读取标签文件中的内容
        if os.path.exists(self.label_file):
            with open(self.label_file, 'r') as f:
                for line in f:
                    info = line.strip('\r\n')
                    if len(info) == 0:
                        continue
                    domains = info.split(' ')
                    name = domains[0]
                    boxes = []
                    img_path = os.path.join(self.image_dir, name)
                    if not os.path.exists(img_path):
                        print('error:', img_path, 'not exist, ignore it')
                        continue

                    if len(domains) > 1:
                        boxes_str = domains[1:]
                        assert (len(boxes_str) % 5 == 0)
                        box_count = int(len(boxes_str) / 5)
                        for i in range(box_count):
                            box_str = boxes_str[i * 5:(i + 1) * 5]
                            box = [float(x) for x in box_str]
                            boxes.append(box)
                    self.label_info[name] = boxes

        # 获取图像文件夹中的所有图片，并确保所有图片都有标签信息
        try:
            image_files = os.listdir(self.image_dir)
            image_files = [img_name for img_name in image_files if img_name.lower().endswith(('.jpg', '.png'))]
            for img_name in image_files:
                if img_name not in self.label_info:
                    self.label_info[img_name] = []

            # 计算 total_batch
            self.total_batch = math.ceil(len(self.label_info.keys()) / self.total)
        except FileNotFoundError:
            QMessageBox.warning(self, "错误", "数据文件夹不存在。请检查项目结构或重新创建项目。", QMessageBox.Ok)
            settings = QSettings("MyCompany", "AnnotationTool")
            settings.remove("last_project")
            self.comboBox_projectName.setCurrentIndex(-1)
            self.comboBox_projectName.clearEditText()
            self.comboBox_projectName.setEditText("")
            for image_widget in self.image_widgets:
                image_widget.set_info(None, None)
            return

    def write_label_file(self):
        """写入标签文件。"""
        if self.label_file == '':
            return
        with open(self.label_file, 'w') as f:
            for key in self.label_info.keys():
                info = str(key)
                if self.label_info[key]:
                    for box in self.label_info[key]:
                        info += ' %.4f %.4f %.4f %.4f %.4f' % (box[0], box[1], box[2], box[3], box[4])
                f.write(info + '\n')

    def save_box_info(self):
        """保存标注框信息。"""
        for image_win in self.image_widgets:
            name, boxes = image_win.get_info()
            if name is not None and len(name) > 0:
                self.label_info[name] = boxes

    def show_context_menu(self, position):
        """显示标签表格的右键上下文菜单。"""
        menu = QMenu(self)
        delete_action = QAction('删除', self)
        menu.addAction(delete_action)

        delete_action.triggered.connect(self.delete_category)
        self.selected_row = self.tableWidget_labels.indexAt(position).row()

        # 仅当右击一个有效的行时才显示菜单
        if self.selected_row >= 0:
            menu.exec_(self.tableWidget_labels.viewport().mapToGlobal(position))

    def delete_category(self):
        """删除选中的类别。"""
        if self.selected_row < 0 or self.selected_row >= len(self.categories):
            return
        del self.categories[self.selected_row]
        if self.selected_row < len(self.categories):
            for i in range(self.selected_row, len(self.categories)):
                category_id, category_name  = self.categories[i]
                category_id -= 1
                self.categories[i] = category_id, category_name
        # 更新表格显示
        self.update_label_table()
        # 保存更新后的类别列表
        self.save_categories()
        # 重置选中的行索引
        self.selected_row = -1

    def update_batch_index(self, next=True, pre=False):
        """更新批次索引。"""
        if len(self.label_info.keys()) == 0:
            return None
        assert (next != pre)

        # 计算总批次数
        self.total_batch = math.ceil(len(self.label_info.keys()) / self.total)

        if next:
            if self.batch_index >= self.total_batch - 1:  # 已经是最后一批了
                return None
            self.batch_index += 1  # 跳到下一批
        elif pre:
            if self.batch_index <= 0:  # 已经是第一批了
                return None
            self.batch_index -= 1  # 回到上一批

        # 根据更新后的 batch_index 获取需要显示的图片
        start_idx = self.batch_index * self.total
        end_idx = start_idx + self.total
        image_names = list(self.label_info.keys())[start_idx:end_idx]

        # 更新进度条
        self.progressBar.setValue((self.batch_index / (self.total_batch - 1)) * 100 if self.total_batch > 1 else 100)

        return image_names

    def keyPressEvent(self, event):
        """处理键盘按键事件。"""
        if event.key() == Qt.Key_A or event.key() == Qt.Key_Left:
            self.slot_btn_pre()
        elif event.key() == Qt.Key_D or event.key() == Qt.Key_Right:
            self.slot_btn_next()
        elif event.key() == Qt.Key_S:
            self.skip_to_unlabeled()

