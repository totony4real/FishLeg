import torch
import torch.nn as nn
import numpy as np
from tqdm import tqdm

import time
import os
import sys
import matplotlib.pyplot as plt
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter

from data_utils import read_data_sets

torch.set_default_dtype(torch.float32)

sys.path.append("../src")

from optim.FishLeg import FishLeg, FISH_LIKELIHOODS

seed = 13
torch.manual_seed(seed)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

dataset = read_data_sets("MNIST", "../data/", if_autoencoder=True)

## Dataset
train_dataset = dataset.train
test_dataset = dataset.test

batch_size = 100

train_loader = torch.utils.data.DataLoader(
    train_dataset, batch_size=batch_size, shuffle=True
)

aux_loader = torch.utils.data.DataLoader(
    train_dataset, shuffle=True, batch_size=batch_size
)

test_loader = torch.utils.data.DataLoader(
    test_dataset, batch_size=1000, shuffle=False
)

model = nn.Sequential(
    nn.Linear(784, 1000, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(1000, 500, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(500, 250, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(250, 30, dtype=torch.float32),
    nn.Linear(30, 250, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(250, 500, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(500, 1000, dtype=torch.float32),
    nn.ReLU(),
    nn.Linear(1000, 784, dtype=torch.float32),
).to(device)

likelihood = FISH_LIKELIHOODS["bernoulli"](device=device)

eta_adam = 1e-4

lr = 0.02
beta = 0.9
weight_decay = 1e-5

aux_lr = 2e-3
aux_eps = 1e-8
scale = 1
damping = 0.3
update_aux_every = 10

initialization = "normal"
normalization = True

opt = FishLeg(
        model,
        aux_loader,
        likelihood,
        lr=lr,
        beta=beta,
        weight_decay=weight_decay,
        aux_lr=aux_lr,
        aux_betas=(0.9, 0.999),
        aux_eps=aux_eps,
        fish_scale=scale,
        damping=damping,
        update_aux_every=update_aux_every,
        initialization=initialization,
        device=device,
    )

writer = SummaryWriter()

epochs = 10

for epoch in range(1, epochs + 1):
    with tqdm(train_loader, unit="batch") as tepoch:
        running_loss = 0
        running_test_loss = 0
        for n, (batch_data, batch_labels) in enumerate(tepoch, start=1):
            tepoch.set_description(f"Epoch {epoch}")

            batch_data, batch_labels = batch_data.to(device), batch_labels.to(device)

            opt.zero_grad()
            output = model(batch_data)

            loss = likelihood(output, batch_labels)

            running_loss += loss.item()

            loss.backward()
            opt.step()

            if n % 50 == 0:
                model.eval()

                test_batch_data, test_batch_labels = next(iter(test_loader))
                test_batch_data, test_batch_labels = test_batch_data.to(
                    device
                ), test_batch_labels.to(device)

                test_output = model(test_batch_data)

                test_loss = likelihood(test_output, test_batch_labels)

                running_test_loss += test_loss.item()

                tepoch.set_postfix(loss=loss.item(), test_loss=test_loss.item())
                model.train()

        writer.add_scalar("Loss/train", running_loss / n, epoch)
        writer.add_scalar("Loss/test", running_test_loss * 50 / n, epoch)


