import os
import json
import cv2
import random
import shutil

import yaml
from tqdm import tqdm


class COCOCreater:

    def __init__(self, src_dir, dst_dir):
        self.train_map = {
            "info": {
                "description": "COCO 2017 Dataset",  # 数据集描述
                "url": "http://cocodataset.org",  # 下载地址
                "version": "1.0",  # 版本
                "year": 2017,  # 年份
                "contributor": "COCO Consortium",  # 提供者
                "date_created": "2017/09/01"  # 数据创建日期
            },

            "licenses": [
                {
                    "url": "http://creativecommons.org/licenses/by-nc-sa/2.0/",
                    "id": 1,
                    "name": "Attribution-NonCommercial-ShareAlike License"
                },
            ],

            "images": [],
            "categories": [],
            "annotations": []
        }

        self.val_map = {
            "info": {
                "description": "COCO 2017 Dataset",  # 数据集描述
                "url": "http://cocodataset.org",  # 下载地址
                "version": "1.0",  # 版本
                "year": 2017,  # 年份
                "contributor": "COCO Consortium",  # 提供者
                "date_created": "2017/09/01"  # 数据创建日期
            },

            "licenses": [
                {
                    "url": "http://creativecommons.org/licenses/by-nc-sa/2.0/",
                    "id": 1,
                    "name": "Attribution-NonCommercial-ShareAlike License"
                },
            ],

            "images": [],
            "categories": [],
            "annotations": []
        }

        self.support_formats = ['jpg', 'JPG', 'png', 'PNG']
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.src_label_file = os.path.join(self.src_dir.replace("data",""), 'label.txt')
        self.src_category_file = os.path.join(self.src_dir.replace("data",""), 'categories.txt')
        self.dst_label_dir_train = os.path.join(self.dst_dir, 'labels', 'train2017')
        self.dst_label_dir_val = os.path.join(self.dst_dir, 'labels', 'val2017')
        self._create_dst_struct()

    def read_ori_labels(self):
        print("trans to coco: start read ori labels")
        labels = []
        with open(self.src_label_file, 'r') as f:
            for line in f.readlines():
                labels.append(line.strip('\r\n'))
        random.shuffle(labels)

        self.ori_train_labels = labels[0: int(len(labels) * 0.8)]
        self.ori_val_labels = labels[int(len(labels) * 0.8):]

    def create_train_map(self):
        print("trans to coco: start create train dataset for coco")
        self._create_coco_map(self.ori_train_labels, self.train_map, self.dst_dir_train2017, self.dst_label_dir_train)
        with open(self.instances_train2017, "w") as f:
            json.dump(self.train_map, f)
        return self.max_cls

    def create_val_map(self):
        print("trans to coco: start create val data set for coco")
        self._create_coco_map(self.ori_val_labels, self.val_map, self.dst_dir_val2017, self.dst_label_dir_val)
        with open(self.instances_val2017, "w") as f:
            json.dump(self.val_map, f)

    def _create_coco_map(self, ori_labels, coco_map, img_dst_dir, label_dst_dir):
        self.max_cls = -1
        self.img_id = 0
        self.box_id = 0

        for i, line in enumerate(tqdm(ori_labels)):
            print('trans to coco: %d/%d' % (i + 1, len(ori_labels)))
            self._create_by_line(line.strip('\r\n'), coco_map, img_dst_dir, label_dst_dir)
        print('trans to coco: success')

    def _create_by_line(self, line, coco_map, img_dst_dir, label_dst_dir):
        fileds = line.split(' ')
        img_name = fileds[0]
        assert '.' in img_name, 'img_name do not has . '
        assert img_name.split('.')[-1] in self.support_formats, 'img_name format is not illagle: (%s)' % img_name

        img_path = os.path.join(self.src_dir, img_name)
        img = cv2.imread(img_path)
        assert img is not None, 'img is none, img path is:%s' % img_path
        h, w, c = img.shape
        shutil.copy(img_path, img_dst_dir)

        label_file_path = os.path.join(label_dst_dir, img_name.replace('.jpg', '.txt').replace('.png', '.txt').replace('.JPG', '.txt').replace('.PNG', '.txt'))

        # 添加图像信息到COCO格式
        self._add_image(img_name, h, w, coco_map)

        # 创建YOLO格式标签文件
        with open(label_file_path, 'w') as lf:
            if len(fileds) > 4:
                boxes = fileds[1:]
                assert len(boxes) % 5 == 0
                box_count = int(len(boxes) / 5)
                for i in range(box_count):
                    box = boxes[i * 5:i * 5 + 5]
                    x0 = float(box[0])
                    y0 = float(box[1])
                    x1 = float(box[2])
                    y1 = float(box[3])
                    cls = int(float(box[4]))
                    self._add_cls(cls, coco_map)
                    self._add_box(x0, y0, x1, y1, cls, coco_map)
                    self._add_yolo_box(lf, x0, y0, x1, y1, cls, w, h)
                    self.box_id += 1

        self.img_id += 1

    def _add_cls(self, cls, coco_map):
        if cls > self.max_cls:
            self.max_cls = cls
            coco_map["categories"].append({"supercategory": "type_%d" % cls,
                                           "id": self.max_cls,
                                           "name": "type_%d" % cls})

    def _add_image(self, img_name, h, w, coco_map):
        coco_map["images"].append({"license": 1,
                                   "file_name": "%s" % img_name,
                                   "coco_url": "http://images.cocodataset.org/val2017/000000397133.jpg",
                                   "height": h,
                                   "width": w,
                                   "date_captured": "2013-11-14 17:02:52",
                                   "flickr_url": "http://farm7.staticflickr.com/6116/6255196340_da26cf2c9e_z.jpg",
                                   "id": self.img_id
                                   })

    def _add_box(self, x0, y0, x1, y1, cls, coco_map):
        box_area = (x1 - x0) * (y1 - y0)
        coco_map["annotations"].append({"segmentation": [[x0, y0, x0, y1, x1, y1, x1, y0, x0, y0]],
                                        "area": box_area,
                                        "iscrowd": 0,
                                        "image_id": self.img_id,
                                        "bbox": [x0, y0, x1 - x0, y1 - y0],
                                        "category_id": cls,
                                        "id": self.box_id
                                        })

    def _add_yolo_box(self, label_file, x0, y0, x1, y1, cls, img_w, img_h):
        x_center = (x0 + x1) / 2.0 / img_w
        y_center = (y0 + y1) / 2.0 / img_h
        width = (x1 - x0) / img_w
        height = (y1 - y0) / img_h
        label_file.write(f"{cls} {x_center} {y_center} {width} {height}\n")

    def _create_dst_struct(self):
        assert os.path.exists(self.dst_dir)
        self.dst_dir_images = os.path.join(self.dst_dir, 'images')
        self.dst_dir_train2017 = os.path.join(self.dst_dir_images, 'train2017')
        self.dst_dir_val2017 = os.path.join(self.dst_dir_images, 'val2017')
        self.dst_dir_annotations = os.path.join(self.dst_dir, 'annotations')
        self.instances_train2017 = os.path.join(self.dst_dir_annotations, 'instances_train2017.json')
        self.instances_val2017 = os.path.join(self.dst_dir_annotations, 'instances_val2017.json')

        if not os.path.exists(self.dst_dir_images):
            os.mkdir(self.dst_dir_images)
        if not os.path.exists(self.dst_dir_train2017):
            os.mkdir(self.dst_dir_train2017)
        if not os.path.exists(self.dst_dir_val2017):
            os.mkdir(self.dst_dir_val2017)
        if not os.path.exists(self.dst_dir_annotations):
            os.mkdir(self.dst_dir_annotations)
        if not os.path.exists(self.dst_label_dir_train):
            os.makedirs(self.dst_label_dir_train)
        if not os.path.exists(self.dst_label_dir_val):
            os.makedirs(self.dst_label_dir_val)

    def create_dataset_yaml(self):
        """
        自动生成dataset.yaml文件，类别名称从categories.txt文件中读取
        """
        print("trans to coco: start creating dataset.yaml file")

        # 读取类别文件
        category_names = []
        with open(self.src_category_file, 'r') as f:
            for line in f.readlines():
                line = line.split(" ")
                category_names.append(line[1].strip())

        # 设置 dataset.yaml 文件内容
        dataset_yaml_content = {
            'train': './images/train2017',
            'val': './images/val2017',
            'nc': len(category_names),
            'names': category_names
        }

        # 写入 dataset.yaml 文件
        dataset_yaml_path = os.path.join(self.dst_dir, 'dataset.yaml')
        with open(dataset_yaml_path, 'w') as yaml_file:
            yaml.dump(dataset_yaml_content, yaml_file, default_flow_style=False, allow_unicode=True)

        print(f"dataset.yaml file created at {dataset_yaml_path}")


if __name__ == '__main__':
    coco = COCOCreater('./third_bridge_0', '../ttt')
    coco.read_ori_labels()
    coco.create_train_map()
    coco.create_val_map()
