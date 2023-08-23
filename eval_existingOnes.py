import os
import cv2
import argparse
from glob import glob
from tqdm import tqdm
import prettytable as pt
import numpy as np

from evaluation.evaluate import evaluator
from config import Config


config = Config()


def do_eval(opt):
    # evaluation for whole dataset
    for _data_name in opt.data_lst:
        print('#' * 20, _data_name, '#' * 20)
        filename = os.path.join(opt.save_dir, '{}_eval.txt'.format(_data_name))
        with open(filename, 'w+') as file_to_write:
            tb = pt.PrettyTable()
            tb.field_names = ["Dataset", "Method", "Smeasure", "wFmeasure", "MAE", "adpEm", "meanEm", "maxEm", "adpFm", "meanFm", "maxFm"]
            for _model_name in opt.model_lst[:]:
                gt_src = os.path.join(opt.gt_root, _data_name)
                gt_paths = glob(os.path.join(gt_src, 'gt', '*'))
                pred_paths = [p.replace(opt.gt_root, os.path.join(opt.pred_root, _model_name)).replace('/gt/', '/') for p in gt_paths]
                # print(pred_paths[:2])
                try:
                    em, sm, fm, mae, wfm = evaluator(
                        gt_pth_lst=gt_paths,
                        pred_pth_lst=pred_paths
                    )
                except:
                    em, sm, fm, mae, wfm = {'curve': np.array([np.float64(-1)]), 'adp': np.float64(-1)}, np.float64(-1), {'curve': np.array([np.float64(-1)]), 'adp': np.float64(-1)}, np.float64(-1), np.float64(-1)
                tb.add_row([_data_name, _model_name, sm.round(3), wfm.round(3), mae.round(3), em['adp'].round(3),
                            em['curve'].mean().round(3), em['curve'].max().round(3), fm['adp'].round(3),
                            fm['curve'].mean().round(3), fm['curve'].max().round(3)])
            print(tb)
            file_to_write.write(str(tb))
            file_to_write.close()


if __name__ == '__main__':
    # set parameters
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--gt_root', type=str, help='ground-truth root',
        default=os.path.join(config.data_root_dir, config.dataset))
    parser.add_argument(
        '--pred_root', type=str, help='prediction root',
        default='./e_preds')
    parser.add_argument(
        '--data_lst', type=list, help='test dataset',
        default={
            'DIS5K': ['DIS-VD', 'DIS-TE1', 'DIS-TE2', 'DIS-TE3', 'DIS-TE4'],
            'COD10K-v3_CAMO-v1': ['COD10K', 'NC4K', 'CAMO', 'CHAMELEON'][:]
        }[config.dataset])
    parser.add_argument(
        '--model_lst', type=str, help='candidate competitors',
        default=glob(os.path.join('ckpt', '*'))[0])
    parser.add_argument(
        '--save_dir', type=str, help='candidate competitors',
        default='e_result')
    parser.add_argument(
        '--check_integrity', type=bool, help='whether to check the file integrity',
        default=False)
    opt = parser.parse_args()

    os.makedirs(opt.save_dir, exist_ok=True)
    opt.model_lst = sorted(['--'.join(m.rstrip('.pth').split(os.sep)[-2:]) for m in glob(os.path.join(opt.model_lst, '*.pth'))], key=lambda x: int(x.split('ep')[-1]), reverse=True)

    # check the integrity of each candidates
    if opt.check_integrity:
        for _data_name in opt.data_lst:
            for _model_name in opt.model_lst:
                gt_pth = os.path.join(opt.gt_root, _data_name)
                pred_pth = os.path.join(opt.pred_root, _model_name, _data_name)
                if not sorted(os.listdir(gt_pth)) == sorted(os.listdir(pred_pth)):
                    print(len(sorted(os.listdir(gt_pth))), len(sorted(os.listdir(pred_pth))))
                    print('The {} Dataset of {} Model is not matching to the ground-truth'.format(_data_name, _model_name))
    else:
        print('>>> skip check the integrity of each candidates')

    # start engine
    do_eval(opt)