import numpy as np
import os
import torch
import torch.nn as nn
import torch.utils.data as Data

from a import load_data
from b import save_to_file
from torch.autograd import Variable
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import scale
from tqdm import tqdm


use_cuda = torch.cuda.is_available()


class NN(nn.Module):
    def __init__(self, input_size, num_units, label_size):
        super(NN, self).__init__()
        self.layer = nn.Sequential(
            nn.Linear(input_size, num_units),
            nn.Sigmoid(),
            nn.Linear(num_units, label_size)
        )

    def forward(self, x):
        x = self.layer(x)
        return x


def gen_index_for_labels(labels):
    labels = list(set(labels))
    l2i = {}
    i2l = {}
    for label in labels:
        if label not in l2i:
            l2i[label] = len(l2i)
            i2l[l2i[label]] = label
    return l2i, i2l


def lables_2_index(labels, l2i):
    indices = []
    for label in labels:
        indices.append(l2i[label])
    return np.array(indices)


def index_2_labels(indices, i2l):
    labels = []
    for index in indices:
        labels.append(i2l[index])
    return np.array(labels)


train_data, train_labels = load_data("dataset/train")
train_data = scale(train_data)
test_data, test_labels = load_data("dataset/test")
test_data = scale(test_data)
l2i, i2l = gen_index_for_labels(train_labels)
train_labels = lables_2_index(train_labels, l2i)
# splitting into train and dev
train_data, dev_data, train_labels, dev_labels = train_test_split(train_data, train_labels, random_state=64, test_size=0.20)

# Converting to torch variables
train_data = torch.from_numpy(train_data).type(torch.FloatTensor)
train_labels = torch.from_numpy(train_labels).type(torch.LongTensor)

dev_data = torch.from_numpy(dev_data).type(torch.FloatTensor)
dev_labels = torch.from_numpy(dev_labels).type(torch.LongTensor)

test_data = torch.from_numpy(test_data).type(torch.FloatTensor)

if use_cuda:
    train_data = train_data.cuda()
    train_labels = train_labels.cuda()
    dev_data = dev_data.cuda()
    dev_labels = dev_labels.cuda()
    test_data = test_data.cuda()


def train(epochs, batch_size, model_file, input_size, hidden_units, label_size):
    model = NN(input_size, hidden_units, label_size)
    if os.path.exists(model_file):
        print("Loading Model: %s" % (model_file))
        model.load_state_dict(torch.load(model_file, map_location=lambda storage, loc: storage))

    if use_cuda:
        model = model.cuda()

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_func = nn.CrossEntropyLoss()  # taking softmax and log likelihood
    dataset = torch.utils.data.TensorDataset(train_data, train_labels)
    train_loader = Data.DataLoader(dataset=dataset, batch_size=batch_size, shuffle=True)

    best_dev = 0
    for epoch in range(epochs):
        model.train()
        gold = []
        pred = []
        epoch_loss = []
        for x, y in train_loader:
            b_x = Variable(x)
            b_y = Variable(y)

            if use_cuda:
                b_x = b_x.cuda()
                b_y = b_y.cuda()
            # b_y = b_y.view(b_y.size(0))

            outputs = model(b_x)  # output of the cnn
            loss = loss_func(outputs, b_y)  # loss
            optimizer.zero_grad()  # clearing gradients
            loss.backward()  # backpropogation
            optimizer.step()  # applygradients

            cur_pred = torch.max(outputs, dim=1)[1].data.cpu().numpy().tolist()
            cur_gold = b_y.data.cpu().numpy().tolist()
            gold.extend(cur_gold)
            pred.extend(cur_pred)
            epoch_loss.extend(loss)

        accuracy = accuracy_score(gold, pred) * 100
        loss = np.mean(np.array(epoch_loss))
        dev_pred = test(100, "nn.model", len(train_data[0]), hidden_units, len(l2i), dev_data, model)
        dev_gold = dev_labels.cpu().numpy().tolist()
        dev_accuracy = accuracy_score(dev_gold, dev_pred) * 100

        if dev_accuracy > best_dev:
            print("Saving Model")
            torch.save(model.state_dict(), model_file)
            best_dev = dev_accuracy
            improved = "*"
        else:
            improved = ""

        print('\b\n\nEpoch: ', epoch, '| train loss: %.4f' % loss, '| train_accuracy: %.2f' % accuracy, '| dev_accuracy: %.2f%s' % (dev_accuracy, improved))


def test(batch_size, model_file, input_size, hidden_units, label_size, data, model=None):

    if model is None:
        model = NN(input_size, hidden_units, label_size)
        if os.path.exists(model_file):
            print("Loading Model: %s" % (model_file))
            model.load_state_dict(torch.load(model_file, map_location=lambda storage, loc: storage))
        else:
            print("Model does not exist")
            return []

    if use_cuda:
        model = model.cuda()

    model.eval()

    pred = []
    for i in range(0, len(data), batch_size):
        x = data[i:i + batch_size]
        b_x = Variable(x, volatile=True)
        if use_cuda:
            b_x = b_x.cuda()
        # b_y = b_y.view(b_y.size(0))

        outputs = model(b_x)  # output of the cnn
        cur_pred = torch.max(outputs, dim=1)[1].data.cpu().numpy().tolist()
        pred.extend(cur_pred)

    return pred


hidden_units = 1000
train(100, 10000, "nn.model", len(train_data[0]), hidden_units, len(l2i))
pred = test(100, "nn.model", len(train_data[0]), hidden_units, len(l2i), test_data)
save_to_file(index_2_labels(pred, i2l), "out.txt")