from torch.utils.data import Dataset
from .preprocess import bert_encode
import pandas as pd 
import torch
import os 

class ReviewDataset(Dataset):
    def __init__(self, file_name, args):
        self.args = args
        self.review_df = pd.read_hdf(os.path.join(args["data_chunks_dir"], file_name))
        self.start = int(file_name.split(".")[0].split("_")[2].split("-")[0]) # ex: "filtered_reviews_500-599.h5" -> 500
      
    def __getitem__(self,idx):
        idx = idx + self.start
        appId = self.review_df["AppID"][idx]
        userId = self.review_df["UserID"][idx]
        sentences = self.review_df["SplitReview"]
        review_emb = torch.from_numpy(self.review_df["SplitReview_emb"][idx])
        # review_emb = bert_encode(sentences[idx], self.args)

        y = self.review_df["Like"][idx]
        return appId, userId, review_emb, y

    def __len__(self):
        return len(self.review_df)