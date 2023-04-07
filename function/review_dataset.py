import os 
import torch
import numpy as np
import pandas as pd 
from torch.utils.data import Dataset

class ReviewDataset(Dataset):
    def __init__(self, args, *, target):
        self.args = args
        if target =="train":
            self.review_df = pd.read_pickle(args["train_data_dir"])
        elif target =="val":
            self.review_df = pd.read_pickle(args["val_data_dir"])
        self.user_mf_df = pd.read_pickle(args["user_mf_data_dir"])
        self.item_mf_df = pd.read_pickle(args["item_mf_data_dir"])
        # self.start = int(file_name.split(".")[0].split("_")[2].split("-")[0]) # ex: "filtered_reviews_500-599.h5" -> 500
      
    def __getitem__(self, idx):

        userId = self.review_df["UserID"][idx]
        itemId = self.review_df["AppID"][idx]
        y = self.review_df["Like"][idx]

        user_review_data = pd.read_pickle(os.path.join(self.args["user_data_dir"], str(userId)+".pkl"))
        item_review_data = pd.read_pickle(os.path.join(self.args["item_data_dir"], str(itemId)+".pkl"))

        user_review_emb = torch.from_numpy(np.array(user_review_data["SplitReview_emb"].tolist()))
        item_review_emb = torch.from_numpy(np.array(item_review_data["SplitReview_emb"].tolist()))
        pad_user_emb = torch.zeros(self.args["max_review_user"], user_review_emb.size(1), user_review_emb.size(2))
        pad_item_emb = torch.zeros(self.args["max_review_item"], item_review_emb.size(1), item_review_emb.size(2))

        user_lda_groups = torch.from_numpy(np.array(user_review_data["LDA_group"].tolist()))
        item_lda_groups = torch.from_numpy(np.array(item_review_data["LDA_group"].tolist()))
        pad_user_lda = torch.zeros(self.args["max_review_user"], user_lda_groups.size(1))
        pad_item_lda = torch.zeros(self.args["max_review_item"], item_lda_groups.size(1))

        # Trunc user/item data to max_review_user/max_review_item
        if user_review_emb.size(0) > self.args["max_review_user"]:
            pad_user_emb = user_review_emb[:self.args["max_review_user"], :, :]
        else:
            pad_user_emb[:user_review_emb.size(0), :, :] = user_review_emb

        if item_review_emb.size(0) > self.args["max_review_item"]:
            pad_item_emb = item_review_emb[:self.args["max_review_item"], :, :]
        else:
            pad_item_emb[:item_review_emb.size(0), :, :] = item_review_emb

        if user_lda_groups.size(0) > self.args["max_review_user"]:
            pad_user_lda = user_lda_groups[:self.args["max_review_user"], :]
        else:
            pad_user_lda[:user_lda_groups.size(0), :] = user_lda_groups

        if item_lda_groups.size(0) > self.args["max_review_item"]:
            pad_item_lda = item_lda_groups[:self.args["max_review_item"], :]
        else:
            pad_item_lda[:item_lda_groups.size(0), :] = item_lda_groups

        user_mf_emb =  torch.from_numpy(self.user_mf_df[self.user_mf_df["UserID"]==userId]["MF_emb"].values[0])
        item_mf_emb =  torch.from_numpy(self.item_mf_df[self.item_mf_df["AppID"]==itemId]["MF_emb"].values[0])

        return pad_user_emb, pad_item_emb, pad_user_lda, pad_item_lda, user_mf_emb, item_mf_emb, y

    def __len__(self):
        return len(self.review_df)
    

class ReviewDataseStage1(ReviewDataset):
    def __init__(self, args, *, target):
        super().__init__(args, target=target)

    def __getitem__(self, idx):

        userId = self.review_df["UserID"][idx]
        itemId = self.review_df["AppID"][idx]
        # y = self.review_df["Like"][idx]

        user_review_data = pd.read_pickle(os.path.join(self.args["user_data_dir"], str(userId)+".pkl"))
        item_review_data = pd.read_pickle(os.path.join(self.args["item_data_dir"], str(itemId)+".pkl"))

        user_review_emb = torch.from_numpy(np.array(user_review_data["SplitReview_emb"].tolist()))
        item_review_emb = torch.from_numpy(np.array(item_review_data["SplitReview_emb"].tolist()))
        pad_user_emb = torch.zeros(self.args["max_review_user"], user_review_emb.size(1), user_review_emb.size(2))
        pad_item_emb = torch.zeros(self.args["max_review_item"], item_review_emb.size(1), item_review_emb.size(2))

        user_lda_groups = torch.from_numpy(np.array(user_review_data["LDA_group"].tolist()))
        item_lda_groups = torch.from_numpy(np.array(item_review_data["LDA_group"].tolist()))
        pad_user_lda = torch.zeros(self.args["max_review_user"], user_lda_groups.size(1))
        pad_item_lda = torch.zeros(self.args["max_review_item"], item_lda_groups.size(1))

        # Label for stage1 is different
        user_y = torch.from_numpy(np.array(user_review_data["Like"].tolist()))
        item_y = torch.from_numpy(np.array(item_review_data["Like"].tolist()))
        pad_user_y = torch.zeros(self.args["max_review_user"])
        pad_item_y = torch.zeros(self.args["max_review_item"])

        # Trunc user/item data to max_review_user/max_review_item
        if user_review_emb.size(0) > self.args["max_review_user"]:
            pad_user_emb = user_review_emb[:self.args["max_review_user"], :, :]
        else:
            pad_user_emb[:user_review_emb.size(0), :, :] = user_review_emb

        if item_review_emb.size(0) > self.args["max_review_item"]:
            pad_item_emb = item_review_emb[:self.args["max_review_item"], :, :]
        else:
            pad_item_emb[:item_review_emb.size(0), :, :] = item_review_emb

        if user_lda_groups.size(0) > self.args["max_review_user"]:
            pad_user_lda = user_lda_groups[:self.args["max_review_user"], :]
        else:
            pad_user_lda[:user_lda_groups.size(0), :] = user_lda_groups

        if item_lda_groups.size(0) > self.args["max_review_item"]:
            pad_item_lda = item_lda_groups[:self.args["max_review_item"], :]
        else:
            pad_item_lda[:item_lda_groups.size(0), :] = item_lda_groups

        if user_y.size(0) > self.args["max_review_user"]:
            pad_user_y = user_y[:self.args["max_review_user"]]
        else:
            pad_user_y[:user_y.size(0)] = user_y

        if item_y.size(0) > self.args["max_review_item"]:
            pad_item_y = item_y[:self.args["max_review_item"]]
        else:
            pad_item_y[:item_y.size(0)] = item_y

        user_mf_emb = torch.from_numpy(self.user_mf_df[self.user_mf_df["UserID"]==userId]["MF_emb"].values[0])
        item_mf_emb = torch.from_numpy(self.item_mf_df[self.item_mf_df["AppID"]==itemId]["MF_emb"].values[0])

        return pad_user_emb, pad_item_emb, pad_user_lda, pad_item_lda, user_mf_emb, item_mf_emb, pad_user_y, pad_item_y

