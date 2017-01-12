#Copyright (C) 2016 Paolo Galeone <nessuno@nerdz.eu>
# Based on Tensorflow cifar10_train.py file
# https://github.com/tensorflow/tensorflow/blob/r0.11/tensorflow/models/image/cifar10/cifar10_train.py
#
#This Source Code Form is subject to the terms of the Mozilla Public
#License, v. 2.0. If a copy of the MPL was not distributed with this
#file, you can obtain one at http://mozilla.org/MPL/2.0/.
#Exhibit B is not attached; this software is compatible with the
#licenses expressed under Section 1.12 of the MPL v2.
""" Evaluate the model """

import os
from datetime import datetime
import math

import tensorflow as tf
from inputs.utils import InputType
from models.utils import MODEL_SUMMARIES, tf_log, put_kernels_on_grid
from models.Autoencoder import Autoencoder
from models.Classifier import Classifier
from CLIArgs import CLIArgs


def accuracy(checkpoint_dir, model, dataset, input_type, device="/gpu:0"):
    """
    Read latest saved checkpoint and use it to evaluate the model
    Args:
        checkpoint_dir: checkpoint folder
        model: python package containing the model to save
        dataset: python package containing the dataset to use
        input_type: InputType enum, the input type of the input examples
        device: device where to place the model and run the evaluation
    """
    if not isinstance(input_type, InputType):
        raise ValueError("Invalid input_type, required a valid type")

    with tf.Graph().as_default(), tf.device(device):
        # Get images and labels from the dataset
        # Use batch_size multiple of train set size and big enough to stay in GPU
        batch_size = 200
        images, labels = dataset.inputs(
            input_type=input_type, batch_size=batch_size)

        # Build a Graph that computes the logits predictions from the
        # inference model.
        _, logits = model.get(images, dataset.num_classes(), train_phase=False)

        # Calculate predictions.
        correct_predictions = tf.reduce_sum(
            tf.cast(tf.nn.in_top_k(logits, labels, 1), tf.int32))

        saver = tf.train.Saver()
        accuracy_value = 0.0
        with tf.Session(config=tf.ConfigProto(
                allow_soft_placement=True)) as sess:
            ckpt = tf.train.get_checkpoint_state(checkpoint_dir)
            if ckpt and ckpt.model_checkpoint_path:
                # Restores from checkpoint
                saver.restore(sess, ckpt.model_checkpoint_path)
            else:
                print('[!] No checkpoint file found')
                return

            # Start the queue runners.
            coord = tf.train.Coordinator()
            try:
                threads = []
                for queue_runner in tf.get_collection(
                        tf.GraphKeys.QUEUE_RUNNERS):
                    threads.extend(
                        queue_runner.create_threads(
                            sess, coord=coord, daemon=True, start=True))

                num_iter = int(
                    math.ceil(dataset.num_examples(input_type) / batch_size))
                true_count = 0  # Counts the number of correct predictions.
                total_sample_count = num_iter * batch_size
                step = 0
                while step < num_iter and not coord.should_stop():
                    true_count += sess.run(correct_predictions)
                    step += 1

                accuracy_value = true_count / total_sample_count
            except Exception as exc:
                coord.request_stop(exc)
            finally:
                coord.request_stop()

            coord.join(threads)
        return accuracy_value


def error(checkpoint_dir, model, dataset, input_type, device="/gpu:0"):
    """
    Read latest saved checkpoint and use it to evaluate the model
    Args:
        checkpoint_dir: checkpoint folder
        model: python package containing the model to save
        dataset: python package containing the dataset to use
        input_type: InputType enum, the input type of the input examples
        device: device where to place the model and run the evaluation
    """
    if not isinstance(input_type, InputType):
        raise ValueError("Invalid input_type, required a valid type")

    with tf.Graph().as_default(), tf.device(device):
        # Get images and labels from the dataset
        # Use batch_size multiple of train set size and big enough to stay in GPU
        batch_size = 200
        images, _ = dataset.inputs(input_type=input_type, batch_size=batch_size)

        # Build a Graph that computes the reconstructions predictions from the
        # inference model.
        _, reconstructions = model.get(images,
                                       train_phase=False,
                                       l2_penalty=0.0)

        # Calculate loss.
        loss = model.loss(reconstructions, images)

        saver = tf.train.Saver()
        with tf.Session(config=tf.ConfigProto(
                allow_soft_placement=True)) as sess:
            ckpt = tf.train.get_checkpoint_state(checkpoint_dir)
            if ckpt and ckpt.model_checkpoint_path:
                # Restores from checkpoint
                saver.restore(sess, ckpt.model_checkpoint_path)
            else:
                print('[!] No checkpoint file found')
                return

            # Start the queue runners.
            coord = tf.train.Coordinator()
            try:
                threads = []
                for queue_runner in tf.get_collection(
                        tf.GraphKeys.QUEUE_RUNNERS):
                    threads.extend(
                        queue_runner.create_threads(
                            sess, coord=coord, daemon=True, start=True))

                num_iter = int(
                    math.ceil(dataset.num_examples(input_type) / batch_size))
                step = 0
                average_error = 0.0
                while step < num_iter and not coord.should_stop():
                    error_value = sess.run(loss)
                    step += 1
                    average_error += error_value
                average_error /= step
            except Exception as exc:
                coord.request_stop(exc)
            finally:
                coord.request_stop()

            coord.join(threads)
        return average_error


if __name__ == '__main__':
    ARGS, MODEL, DATASET = CLIArgs(
        description="Evaluate the model").parse_eval()
    DATASET.maybe_download_and_extract()

    if isinstance(MODEL, Classifier):
        print('{}: {} accuracy = {:.3f}'.format(
            datetime.now(),
            'test' if ARGS.test else 'validation',
            accuracy(
                ARGS.checkpoint_dir,
                MODEL,
                DATASET,
                InputType.test if ARGS.test else InputType.validation,
                device=ARGS.eval_device)))

    if isinstance(MODEL, Autoencoder):
        print('{}: {} error = {:.3f}'.format(
            datetime.now(),
            'test' if ARGS.test else 'validation',
            error(
                ARGS.checkpoint_dir,
                MODEL,
                DATASET,
                InputType.test if ARGS.test else InputType.validation,
                device=ARGS.eval_device)))