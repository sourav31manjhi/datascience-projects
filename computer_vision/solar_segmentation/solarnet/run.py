import torch
from torch.utils.data import DataLoader

import numpy as np
from pathlib import Path
from tqdm import tqdm

from solarnet.preprocessing import MaskMaker, ImageSplitter
from solarnet.datasets import ClassifierDataset, SegmenterDataset, make_masks
from solarnet.models import Classifier, Segmenter, train_classifier, train_segmenter


class RunTask:

    @staticmethod
    def make_masks():
        mask_maker = MaskMaker()
        mask_maker.process()

    @staticmethod
    def split_images():
        splitter = ImageSplitter()
        splitter.process()

    @staticmethod
    def train_classifier(max_epochs=5, val_size=0.1, test_size=0.1,
                         device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')):

        model = Classifier()
        if device.type != 'cpu': model = model.cuda()
        dataset = ClassifierDataset()

        # make a train and val set
        train_mask, val_mask, test_mask = make_masks(len(dataset), val_size, test_size)

        dataset.add_mask(train_mask)
        train_dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
        val_dataloader = DataLoader(ClassifierDataset(mask=val_mask), batch_size=64, shuffle=True)
        test_dataloader = DataLoader(ClassifierDataset(mask=test_mask), batch_size=64)

        train_classifier(model, train_dataloader, val_dataloader, max_epochs=max_epochs)

        savedir = Path('data/models')
        if not savedir.exists(): savedir.mkdir()
        torch.save(model.state_dict(), savedir / 'classifier.model')

        # save predictions for analysis
        print("Generating test results")
        preds, true = [], []
        with torch.no_grad():
            for test_x, test_y in tqdm(test_dataloader):
                test_preds = model(test_x)
                preds.append(test_preds.squeeze(1).cpu().numpy())
                true.append(test_y.cpu().numpy())

        np.save(savedir / 'classifier_preds.npy', np.concatenate(preds))
        np.save(savedir / 'classifier_true.npy', np.concatenate(true))

    @staticmethod
    def train_segmenter(max_epochs=1, val_size=0.1, test_size=0.1, use_classifier=True,
                        device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')):
        model = Segmenter()
        if device.type != 'cpu': model = model.cuda()

        model_dir = Path('data/models')
        if use_classifier:
            classifier_sd = torch.load(model_dir / 'classifier.model')
            model.load_base(classifier_sd)

        dataset = SegmenterDataset()
        train_mask, val_mask, test_mask = make_masks(len(dataset), val_size, test_size)

        dataset.add_mask(train_mask)
        train_dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
        val_dataloader = DataLoader(SegmenterDataset(mask=val_mask), batch_size=64, shuffle=True)
        test_dataloader = DataLoader(SegmenterDataset(mask=test_mask), batch_size=64)

        train_segmenter(model, train_dataloader, val_dataloader, max_epochs=max_epochs)

        if not model_dir.exists(): model_dir.mkdir()
        torch.save(model.state_dict(), model_dir / 'segmenter.model')

        print("Generating test results")
        images, preds, true = [], [], []
        with torch.no_grad():
            for test_x, test_y in tqdm(test_dataloader):
                test_preds = model(test_x)
                images.append(test_x.cpu().numpy())
                preds.append(test_preds.squeeze(1).cpu().numpy())
                true.append(test_y.cpu().numpy())

        np.save(model_dir / 'segmenter_images.npy', np.concatenate(images))
        np.save(model_dir / 'segmenter_preds.npy', np.concatenate(preds))
        np.save(model_dir / 'segmenter_true.npy', np.concatenate(true))
