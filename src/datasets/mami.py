import os
from collections import defaultdict

from sklearn.model_selection import KFold
from torch.utils.data import Dataset
from transformers import AutoTokenizer
from tabulate import tabulate

output_keys = ['misogynous', 'shaming', 'stereotype', 'objectification', 'violence']

class MisogynyDataset(Dataset):
  def __init__(self, name, data_dir, data, tokenizer, text_max_length, k_folds=5):
    self.name = name
    self.data_dir = data_dir
    self.data = data
    self.tokenizer = tokenizer
    self.text_max_length = text_max_length
    self.k_fold = k_folds
    self.kf = KFold(n_splits=self.k_fold, shuffle=True, random_state=42)
    self.k_splits = list(self.kf.split(self.data))

  def get_kth_fold_dataset(self, k):
    train_data = []
    test_data = []
    train_set, test_set =  self.k_splits[k]
    
    for i in train_set:
      train_data.append(self.data[i])
    for i in test_set:
      test_data.append(self.data[i])

    return MisogynyDataset(f'train_{k}', self.data_dir, train_data, self.tokenizer, self.text_max_length), MisogynyDataset(f'eval_{k}', self.data_dir, test_data, self.tokenizer, self.text_max_length)

  @staticmethod
  def create_mami_dataset_from_files(name, configs, data_dir, text_file, labels_file_path=None):
    data_dict = defaultdict(lambda: {})
    def update_data_from_file(filepath):
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
          keys = None if '.csv' in filepath else ['file_name', 'misogynous', 'shaming', 'stereotype', 'objectification', 'violence']
          for line in f:
            if not keys:
              keys = line.strip().split('\t')
              continue
            
            filename = None
            for index, value in enumerate(line.strip().split('\t')):
              if index == 0:
                filename = value

              data_dict[filename][keys[index]] = value


    update_data_from_file(os.path.join(data_dir, text_file))
    if labels_file_path:
      update_data_from_file(labels_file_path)

    data = list(data_dict.values())

    tokenizer = AutoTokenizer.from_pretrained(configs.model.text.bert, use_fast=False)
    text_max_length = configs.model.text.max_length
    return MisogynyDataset(name, data_dir, data, tokenizer, text_max_length, configs.train.k_fold)
  
  def __len__(self):
    return len(self.data)

        
  def summarize(self):
    return """
---------------------------------------------
Dataset: {}
Data Dir: {}
------------------------
Class wise distribution
------------------------ 
{}
---------------------------------------------
""".format(self.name, self.data_dir, self.get_class_distribution())

  def get_class_distribution(self, return_dict=False):
    class_distribution = defaultdict(int)
    for item in self.data:
      for key in output_keys:
        if item[key] == '1':
          class_distribution[key] += 1

    if return_dict:
      return class_distribution

    class_distribution_table = []
    for key, value in class_distribution.items():
      class_distribution_table.append([key, value])

    return tabulate(class_distribution_table, headers=['Class', 'Count'])

  def __getitem__(self, idx):
    item = self.data[idx]

    encoding = self.tokenizer.encode_plus(
      item['Text Transcription'],
      add_special_tokens=True,
      max_length=self.text_max_length,
      truncation= True,
      return_token_type_ids=False,
      padding = 'max_length',
      return_attention_mask=True,
      return_tensors='pt',
    )

    input = {
        'image': os.path.join(self.data_dir, item['file_name']),
        'text': item['Text Transcription'],
        'input_ids': encoding['input_ids'].flatten(),
        'attention_mask': encoding['attention_mask'].flatten(),
    }

    output = {k:v for k,v in item.items() if k in output_keys}
    return {'input': input, 'output': output}
    