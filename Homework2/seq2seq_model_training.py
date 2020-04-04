# -*- coding: utf-8 -*-
"""seq2seq_model_training.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1nQfYxPLekZVGn_a4RuIGQ_t6A8C6WsHj
"""

# Commented out IPython magic to ensure Python compatibility.
# %tensorflow_version 1.x

import json
from collections import Counter
import os
import numpy as np
import pandas as pd

import tensorflow as tf
import helpers
from tensorflow.python.ops.rnn_cell import LSTMCell, LSTMStateTuple

#Caption Preprocessing
#Creating two python dictionaries, word_to_index and index_to_word
#we will represent every unique word in the vocab by an integer
def vocab():
  filters = '!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n'
  vocab=[]
  captions=[]
  caption_list=[]
  count = []
  file_names=[]
  video_feature_dict={} #dict containing video features for every video ids
  video_caption_dict={} #dict containing captions for every video ids

  with open('training_label.json') as f:
    training_labels = json.load(f)

  for train in training_labels:
    captions.append(train['caption'])
    file_names.append(train['id'])
    video_caption_dict[train['id']] = train['caption'] 
  
  for i in range(len(captions)):
    count.append(len(captions[i]))

  for i in range(len(captions)):
    for j in range(count[i]):
      caption_list.append(captions[i][j])
  

  for files in range(1):
    features = np.load(str(file_names[files])+'.npy')
    video_feature_dict[files] = features

  for w in caption_list:
    for f in filters:
      w = w.replace(f, '')

    words = w.split(' ')
    for v in words:
      vo = v.replace('.','')
      vocab.append(vo)

  c=Counter(vocab)
  unique = [w for w in vocab if c[w] == 1]

  return unique, caption_list, video_feature_dict, video_caption_dict

def indexing(vocab):
  #the vocab here is the unique words from the captions
  ixtoword = {} #index to word
  wordtoix = {} #word to index

  ixtoword[0] = '<pad>'
  ixtoword[1] = '<bos>'
  ixtoword[2] = '<eos>'
  ixtoword[3] = '<unk>'

  wordtoix['<pad>'] = 0
  wordtoix['<bos>'] = 1
  wordtoix['<eos>'] = 2
  wordtoix['<unk>'] = 3

  ix = 0
  for w in vocab:
    wordtoix[w] = ix+4
    ixtoword[ix] = w
    ix += 1
  
  return ixtoword, wordtoix

def caption_details(caption_list):
  cap_length = []
  for i in range(len(caption_list)):
    count = 1
    for x in caption_list[i]:
      if(x == ' '):
        count +=1
    cap_length.append(count)

  print(sum(cap_length)/len(cap_length))

  maximum = max(cap_length)
  average = sum(cap_length)/len(cap_length)

  return maximum, average

def next_feed(batches):
    batch = next(batches)
    encoder_inputs_, encoder_input_lengths_ = helpers.batch(batch)
    decoder_targets_, _ = helpers.batch(
        [(sequence) + [EOS] + [PAD] for sequence in batch]
    )
    return {
        encoder_inputs: encoder_inputs_,
        encoder_inputs_length: encoder_input_lengths_,
        decoder_targets: decoder_targets_,
    }


def training_model(word_size, max_length, feature_length):
  tf.set_random_seed(9487)
  vocab_size = word_size
  encoder_input_size = feature_length
  decoder_output_size = max_length
  encoder_hidden_units = 20
  decoder_hidden_units = 20
  rnn_size = 64

  encoder_inputs = tf.placeholder(shape=(None, None), dtype=tf.int32, name='encoder_inputs')
  encoder_inputs_length = tf.placeholder(shape=(None,), dtype=tf.int32, name='encoder_inputs_length')
  decoder_targets = tf.placeholder(shape=(None, None), dtype=tf.int32, name='decoder_targets')

  embeddings = tf.Variable(tf.random_uniform([vocab_size, encoder_input_size], -1.0, 1.0), dtype=tf.float32)
  encoder_inputs_embedded = tf.nn.embedding_lookup(embeddings, encoder_inputs)

  encoder_cell = LSTMCell(encoder_hidden_units)

  encoder_outputs, encoder_final_state = (tf.nn.dynamic_rnn(cell=encoder_cell,
                      inputs=encoder_inputs_embedded, 
                      sequence_length=encoder_inputs_length,
                      dtype=tf.float32, time_major=True))


  decoder_cell = LSTMCell(decoder_hidden_units)
  encoder_max_time, batch_size = tf.unstack(tf.shape(encoder_inputs))
  decoder_lengths = encoder_inputs_length + 3

  attention_mechanism = tf.contrib.seq2seq.LuongAttention(
                rnn_size, 
                memory=encoder_outputs,
                memory_sequence_length=encoder_inputs_length)
  
  decoder_cell = tf.contrib.seq2seq.AttentionWrapper(
                cell=decoder_cell, 
                attention_mechanism=attention_mechanism, 
                attention_layer_size=rnn_size, 
                name='Attention_Wrapper')

  #weights
  W = tf.Variable(tf.random_uniform([decoder_hidden_units, vocab_size], -1, 1), dtype=tf.float32)
  #bias
  b = tf.Variable(tf.zeros([vocab_size]), dtype=tf.float32)

  eos_time = tf.ones([batch_size], dtype=tf.int32, name='EOS')
  pad_time = tf.zeros([batch_size], dtype=tf.int32, name='PAD')

  #retrieves rows of the params tensor. The behavior is similar to using indexing with arrays in numpy
  embeddings = tf.Variable(tf.random_uniform([vocab_size, decoder_output_size], -1.0, 1.0), dtype=tf.float32)
  decoder_inputs_embedded = tf.nn.embedding_lookup(embeddings, encoder_outputs)

  decoder_outputs, decoder_final_state = (tf.nn.dynamic_rnn(cell=decoder_cell,
                      inputs=decoder_inputs_embedded, 
                      sequence_length= decoder_lengths,
                      dtype=tf.float32, time_major=True))

  decoder_max_steps, decoder_batch_size, decoder_dim = tf.unstack(tf.shape(decoder_outputs))
  decoder_outputs_flat = tf.reshape(decoder_outputs, (-1, decoder_dim))

  decoder_logits_flat = tf.add(tf.matmul(decoder_outputs_flat, W), b)
  decoder_logits = tf.reshape(decoder_logits_flat, (decoder_max_steps, decoder_batch_size, vocab_size))

  decoder_prediction = tf.argmax(decoder_logits, 2)

  stepwise_cross_entropy = tf.nn.softmax_cross_entropy_with_logits(
    labels=tf.one_hot(decoder_targets, depth=vocab_size, dtype=tf.float32),
    logits=decoder_logits,
  )
  #loss function
  loss = tf.reduce_mean(stepwise_cross_entropy)
  #train it 
  train_op = tf.train.AdamOptimizer().minimize(loss)
  sess.run(tf.global_variables_initializer())

  batch_size = 100

  batches = helpers.random_sequences(length_from=3, length_to=8,
                                   vocab_lower=2, vocab_upper=10,
                                   batch_size=batch_size)

  max_batches = 1972

  for batch in range(max_batches):
    fd = next_feed(batches)
    _, l = sess.run([train_op, loss], fd)
    losses.append(l)

  if batch == 0 or batch % 100 == 0:
    print('batch {}'.format(batch))
    print('  minibatch loss: {}'.format(sess.run(loss, fd)))
    predict_ = sess.run(decoder_prediction, fd)
    for i, (inp, pred) in enumerate(zip(fd[encoder_inputs].T, predict_.T)):
      print('    predicted > {}'.format(pred))
      if i >= 2:
        break

if __name__ == "__main__":
  #things to do here
  #getting the video_caption_dict and video_feature_dict
  #getting wordtoix and ixtoword
  #captions_words_set unique words in the captions
  #max_captions_length
  #avg_captions_length
  #num_unique_tokens_captions
  print("This is just a start")
  unique_words, caption_list, video_feature_dict, video_caption_dict = vocab()
  ixtoword, wordtoix = indexing(unique_words)
  max_captions_length, average_captions_length = caption_details(caption_list)
  unique_words_count = len(unique_words)


  print("Maximum Caption Length",max_captions_length)
  print("Average Caption Length",average_captions_length)
  print("Total number of unique words",unique_words_count)

  training_model(unique_words_count, max_captions_length, len(video_feature_dict))