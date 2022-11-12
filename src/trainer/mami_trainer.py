import json
from turtle import pos
from tqdm import tqdm

from sklearn.metrics import classification_report

from torch.nn import BCEWithLogitsLoss
from torch import Tensor, sigmoid

from src.datasets.mami import output_keys
from src.trainer.trainer import Trainer
from src.utils.mami import calculate

class MamiTrainer(Trainer):
    def __init__(self, get_model_func, configs, train_dataset, test_dataset, device, logger) -> None:
        super().__init__(get_model_func, configs, train_dataset, test_dataset, device, logger)
        pos_weights = Tensor([0.5/(self.configs.datasets.mami.train.configs[k]) for k in output_keys]).to(self.device)
        self.bce_loss = BCEWithLogitsLoss(pos_weight=pos_weights)
        

    def summarize_scores(self, scores):
        sum_scores = 0
        for output_key in output_keys[1:]:
            sum_scores += scores[output_key][output_key]['f1-score']

        summarized_scores = sum_scores / len(output_keys) - 1
        return summarized_scores

    def train(self, train_dataloader):
        self.model.train()
        print('*' * 50)
        actual_labels = {k:[] for k in output_keys}
        predicted_labels = {k:[] for k in output_keys}
        total_loss = 0
        
        for batch in tqdm(train_dataloader):
            pred = self.model(batch['input'])
            actual_output = calculate(pred, batch['output'], actual_labels, predicted_labels)
            actual_output = Tensor(actual_output).to(self.device)                            
            loss = self.bce_loss(pred, actual_output)
            total_loss += loss.item()

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        return total_loss


    def eval(self, test_dataloader):
        self.model.eval()
        actual_labels = {k:[] for k in output_keys}
        predicted_labels = {k:[] for k in output_keys}

        predictions = {}
        for batch in tqdm(test_dataloader):
            pred = self.model(batch['input'])
            calculate(pred, batch['output'], actual_labels, predicted_labels)

            for image_path, scores in zip(batch['input']['image'] , sigmoid(pred).tolist()):
                predictions[image_path] = {k: v for k, v in zip(output_keys, scores)}

        log_dict = {}
        for k in output_keys:
            log_dict[k] = classification_report(actual_labels[k], predicted_labels[k], target_names=[f'!{k}', k], output_dict=True)

        return log_dict, predictions
    
    def predict(self, test_dataloader):
        self.model.eval()

        predictions = {}
        for batch in tqdm(test_dataloader):
            pred = self.model(batch['input'])

            for image_path, scores in zip(batch['input']['image'] , sigmoid(pred).tolist()):
                predictions[image_path] = {k: v for k, v in zip(output_keys, scores)}

        return predictions