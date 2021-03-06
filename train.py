import os
import json
import utils
import torch
import argparse
import time
from layers import Seq2SeqAttention

parser = argparse.ArgumentParser(description='Selective Encoding for Abstractive Sentence Summarization in DyNet')

parser.add_argument('--gpu', type=int, default='1', help='GPU ID to use. For cpu, set -1 [default: -1]')
parser.add_argument('--n_epochs', type=int, default=1, help='Number of epochs [default: 3]')
parser.add_argument('--n_train', type=int, default=600000,
					help='Number of training data (up to 3803957 in gigaword) [default: 3803957]')
parser.add_argument('--n_valid', type=int, default=189651,
					help='Number of validation data (up to 189651 in gigaword) [default: 189651])')
parser.add_argument('--batch_size', type=int, default=32, help='Mini batch size [default: 32]')
parser.add_argument('--emb_dim', type=int, default=200, help='Embedding size [default: 256]')
parser.add_argument('--hid_dim', type=int, default=256, help='Hidden state size [default: 256]')
parser.add_argument('--maxout_dim', type=int, default=2, help='Maxout size [default: 2]')
parser.add_argument('--model_file', type=str, default='./models/params_0.pkl')
args = parser.parse_args()

model_dir = './models'
if not os.path.exists(model_dir):
	os.mkdir(model_dir)

device = torch.device(("cuda:%d" % args.gpu) if args.gpu != -1 else "cpu")
print('using device', device)


def validate(validX, validY, model):
	with torch.no_grad():
		for _, (batchX, batchY) in enumerate(zip(validX, validY)):
			batchX = torch.tensor(batchX, dtype=torch.long, device=device)
			batchY = torch.tensor(batchY, dtype=torch.long, device=device)
			loss = model(batchX, batchY).cpu().numpy()
			return loss


def train(trainX, trainY, validX, validY, model, optimizer, scheduler, epochs=1):
	steps = 0
	counts = 1
	start = time.time()
	for epoch in range(epochs):
		for _, (batchX, batchY) in enumerate(zip(trainX, trainY)):
			optimizer.zero_grad()

			batchX = torch.tensor(batchX, dtype=torch.long, device=device)
			batchY = torch.tensor(batchY, dtype=torch.long, device=device)
			loss = model(batchX, batchY)
			loss.backward(retain_graph=True)

			torch.nn.utils.clip_grad_value_(model.parameters(), 20)

			optimizer.step()
			scheduler.step()

			steps += 1
			if steps % 10 == 0:
				train_loss = loss.cpu().detach().numpy()
				valid_loss = validate(validX, validY, model)
				# print('step %d, training loss = %f' % (steps, train_loss))
				print('step %d, training loss = %f, validation loss = %f' % (steps, train_loss, valid_loss))

				if steps*trainX.batch_size % 320000 == 0:
					torch.save(model.state_dict(), os.path.join(model_dir, 'params_%d.pkl' % counts))
					print('Model saved in dir %s' % model_dir)
					counts += 1

		validate(validX, validY, model)
		# torch.save(model, 'model_%d.pkl' % epoch)
		torch.save(model.state_dict(), os.path.join(model_dir, 'params_%d.pkl' % epoch))
		print('Model saved in dir %s' % model_dir)
	end = time.time()
	span = end - start
	print('%dh%dmin spent on training' % (int(span / 3600), int(span % 3600) / 60))


def main():
	print(args)

	N_EPOCHS = args.n_epochs
	N_TRAIN = args.n_train
	N_VALID = args.n_valid
	BATCH_SIZE = args.batch_size
	EMB_DIM = args.emb_dim
	HID_DIM = args.hid_dim
	MAXOUT_DIM = args.maxout_dim

	TRAIN_X = 'PART_I.article'
	TRAIN_Y = 'PART_I.summary'
	VALID_X = 'PART_III.article'
	VALID_Y = 'PART_III.summary'

	trainX = utils.getDataLoader(TRAIN_X, max_len=100, n_data=N_TRAIN, batch_size=BATCH_SIZE)
	trainY = utils.getDataLoader(TRAIN_Y, max_len=25, n_data=N_TRAIN, batch_size=BATCH_SIZE)
	validX = utils.getDataLoader(VALID_X, max_len=100, n_data=N_VALID, batch_size=BATCH_SIZE)
	validY = utils.getDataLoader(VALID_Y, max_len=25, n_data=N_VALID, batch_size=BATCH_SIZE)

	vocab = json.load(open('data/vocab.json'))
	model = Seq2SeqAttention(len(vocab), EMB_DIM, HID_DIM, BATCH_SIZE, vocab, device, max_trg_len=25).cuda(device)

	model_file = args.model_file
	if os.path.exists(model_file):
		file = os.path.join(model_dir, os.listdir(model_dir)[-1])
		model.load_state_dict(torch.load(model_file))
		print('Load model parameters from %s' % model_file)

	optimizer = torch.optim.SGD(model.parameters(), lr=1e-2)
	scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=20000, gamma=0.3)

	train(trainX, trainY, validX, validY, model, optimizer, scheduler, N_EPOCHS)


if __name__ == '__main__':
	main()

