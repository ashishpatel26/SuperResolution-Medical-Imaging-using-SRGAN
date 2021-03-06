#! /usr/bin/python
# -*- coding: utf8 -*-

import os, time, pickle, random, time
from datetime import datetime
import numpy as np
from time import localtime, strftime
import logging, scipy

import tensorflow as tf
import tensorlayer as tl
from model import SRGAN_g, SRGAN_d, Vgg19_simple_api
from utils import *
from config import config, log_config

###====================== HYPER-PARAMETERS ===========================###
## Adam
batch_size = config.TRAIN.batch_size
lr_init = config.TRAIN.lr_init
beta1 = config.TRAIN.beta1
## initialize G
n_epoch_init = config.TRAIN.n_epoch_init
## adversarial learning (SRGAN)
n_epoch = config.TRAIN.n_epoch
lr_decay = config.TRAIN.lr_decay
decay_every = config.TRAIN.decay_every

ni = int(np.sqrt(batch_size))


def train():
    ## create folders to save result images and trained model
    save_dir_ginit = "samples/{}_ginit".format(tl.global_flag['mode'])
    save_dir_gan = "samples/{}_gan".format(tl.global_flag['mode'])
    tl.files.exists_or_mkdir(save_dir_ginit)
    tl.files.exists_or_mkdir(save_dir_gan)
    checkpoint_dir = "checkpoint"  # checkpoint_resize_conv
    tl.files.exists_or_mkdir(checkpoint_dir)

    ###====================== PRE-LOAD DATA ===========================###
    train_hr_img_list = sorted(tl.files.load_file_list(path=config.TRAIN.hr_img_path, regx='.*.png', printable=False))
    train_lr_img_list = sorted(tl.files.load_file_list(path=config.TRAIN.lr_img_path, regx='.*.png', printable=False))
    valid_hr_img_list = sorted(tl.files.load_file_list(path=config.VALID.hr_img_path, regx='.*.png', printable=False))
    valid_lr_img_list = sorted(tl.files.load_file_list(path=config.VALID.lr_img_path, regx='.*.png', printable=False))

    ## If your machine have enough memory, please pre-load the whole train set.
    print(train_hr_img_list)
    print("reading images")
    #train_hr_imgs = tl.vis.read_images(train_hr_img_list, path=config.TRAIN.hr_img_path, n_threads=32)
    #for im in train_hr_imgs:
    #     print("im.shape:", im.shape)
    
    
    #sci_img = scipy.misc.imread(os.path.join(config.TRAIN.hr_img_path, train_hr_img_list[0]), mode='L')
    #print("sci_img:", type(sci_img), sci_img.shape)
    
    #print(type(train_hr_imgs), len(train_hr_img_list))

    train_hr_imgs = [] #[None] * len(train_hr_img_list)
    
    #sess = tf.Session()
    for img__ in train_hr_img_list:
        
        #file_contents = tf.read_file(config.TRAIN.hr_img_path + img__)
        #example = tf.image.decode_png(file_contents, channels=1)

        #train_hr_imgs.append(sess.run(example))
        
        image_loaded = scipy.misc.imread(os.path.join(config.TRAIN.hr_img_path, img__), mode='L')
        image_loaded = image_loaded.reshape((image_loaded.shape[0], image_loaded.shape[1], 1))
        #print("image_loaded:", image_loaded.shape)

        #scipy.misc.imsave(img__ + '-verify.png', image_loaded)

        '''fname = img__ + '-verify.png'
        print("fname:", fname)
        print("shape now:", type(image_loaded[:, :, 0])) #.shape())
        scipy.misc.toimage(image_loaded[:, :, 0]).save(img__ + '-verify.png') #, cmin=0, cmax=255).save("tmp.png")
        '''

        train_hr_imgs.append(image_loaded)
    
    print(type(train_hr_imgs), len(train_hr_img_list))
            
    # valid_lr_imgs = tl.vis.read_images(valid_lr_img_list, path=config.VALID.lr_img_path, n_threads=32)
    # for im in valid_lr_imgs:
    #     print(im.shape)
    # valid_hr_imgs = tl.vis.read_images(valid_hr_img_list, path=config.VALID.hr_img_path, n_threads=32)
    # for im in valid_hr_imgs:
    #     print(im.shape)
    # exit()

    ###========================== DEFINE MODEL ============================###
    ## train inference

    #t_image = tf.placeholder('float32', [batch_size, 96, 96, 3], name='t_image_input_to_SRGAN_generator')
    #t_target_image = tf.placeholder('float32', [batch_size, 384, 384, 3], name='t_target_image')
    
    t_image = tf.placeholder('float32', [batch_size, 56, 56, 1], name='t_image_input_to_SRGAN_generator')
    t_target_image = tf.placeholder('float32', [batch_size, 224, 224, 1], name='t_target_image') # may have to convert 224x224x1 into 224x224x3, with channel 1 & 2 as 0. May have to have separate place-holder ?

    print("t_image:", tf.shape(t_image))
    print("t_target_image:", tf.shape(t_target_image))
    
    net_g = SRGAN_g(t_image, is_train=True, reuse=False)
    
    print("net_g.outputs:", tf.shape(net_g.outputs))
    
    net_d, logits_real = SRGAN_d(t_target_image, is_train=True, reuse=False)
    _, logits_fake = SRGAN_d(net_g.outputs, is_train=True, reuse=True)

    net_g.print_params(False)
    net_g.print_layers()
    net_d.print_params(False)
    net_d.print_layers()

    ## vgg inference. 0, 1, 2, 3 BILINEAR NEAREST BICUBIC AREA
    t_target_image_224 = tf.image.resize_images(
        t_target_image, size=[224, 224], method=0,
        align_corners=False)  # resize_target_image_for_vgg # http://tensorlayer.readthedocs.io/en/latest/_modules/tensorlayer/layers.html#UpSampling2dLayer
    t_predict_image_224 = tf.image.resize_images(net_g.outputs, size=[224, 224], method=0, align_corners=False)  # resize_generate_image_for_vgg

    
    ## Added as VGG works for RGB and expects 3 channels.
    t_target_image_224 = tf.image.grayscale_to_rgb(t_target_image_224)
    t_predict_image_224 = tf.image.grayscale_to_rgb(t_predict_image_224)
    
    print("net_g.outputs:", tf.shape(net_g.outputs))
    print("t_predict_image_224:", tf.shape(t_predict_image_224))
    
    net_vgg, vgg_target_emb = Vgg19_simple_api((t_target_image_224 + 1) / 2, reuse=False)
    _, vgg_predict_emb = Vgg19_simple_api((t_predict_image_224 + 1) / 2, reuse=True)

    ## test inference
    net_g_test = SRGAN_g(t_image, is_train=False, reuse=True)

    # ###========================== DEFINE TRAIN OPS ==========================###
    d_loss1 = tl.cost.sigmoid_cross_entropy(logits_real, tf.ones_like(logits_real), name='d1')
    d_loss2 = tl.cost.sigmoid_cross_entropy(logits_fake, tf.zeros_like(logits_fake), name='d2')
    d_loss = d_loss1 + d_loss2

    g_gan_loss = 1e-3 * tl.cost.sigmoid_cross_entropy(logits_fake, tf.ones_like(logits_fake), name='g')
    mse_loss = tl.cost.mean_squared_error(net_g.outputs, t_target_image, is_mean=True)
    vgg_loss = 2e-6 * tl.cost.mean_squared_error(vgg_predict_emb.outputs, vgg_target_emb.outputs, is_mean=True)

    g_loss = mse_loss + vgg_loss + g_gan_loss

    d_loss1_summary = tf.summary.scalar('Disciminator logits_real loss', d_loss1)
    d_loss2_summary = tf.summary.scalar('Disciminator logits_fake loss', d_loss2)
    d_loss_summary = tf.summary.scalar('Disciminator total loss', d_loss)
    
    g_gan_loss_summary = tf.summary.scalar('Generator GAN loss', g_gan_loss)
    mse_loss_summary = tf.summary.scalar('Generator MSE loss', mse_loss)
    vgg_loss_summary = tf.summary.scalar('Generator VGG loss', vgg_loss)
    g_loss_summary = tf.summary.scalar('Generator total loss', g_loss)

    g_vars = tl.layers.get_variables_with_name('SRGAN_g', True, True)
    d_vars = tl.layers.get_variables_with_name('SRGAN_d', True, True)

    with tf.variable_scope('learning_rate'):
        lr_v = tf.Variable(lr_init, trainable=False)
    ## Pretrain
    g_optim_init = tf.train.AdamOptimizer(lr_v, beta1=beta1).minimize(mse_loss, var_list=g_vars)
    ## SRGAN
    g_optim = tf.train.AdamOptimizer(lr_v, beta1=beta1).minimize(g_loss, var_list=g_vars)
    d_optim = tf.train.AdamOptimizer(lr_v, beta1=beta1).minimize(d_loss, var_list=d_vars)

    ###========================== RESTORE MODEL =============================###
    sess = tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False))
    tl.layers.initialize_global_variables(sess)
    if tl.files.load_and_assign_npz(sess=sess, name=checkpoint_dir + '/g_{}.npz'.format(tl.global_flag['mode']), network=net_g) is False:
        tl.files.load_and_assign_npz(sess=sess, name=checkpoint_dir + '/g_{}_init.npz'.format(tl.global_flag['mode']), network=net_g)
    tl.files.load_and_assign_npz(sess=sess, name=checkpoint_dir + '/d_{}.npz'.format(tl.global_flag['mode']), network=net_d)

    ###============================= LOAD VGG ===============================###
    vgg19_npy_path = "vgg19.npy"
    if not os.path.isfile(vgg19_npy_path):
        print("Please download vgg19.npz from : https://github.com/machrisaa/tensorflow-vgg")
        exit()
    npz = np.load(vgg19_npy_path, encoding='latin1').item()

    params = []
    for val in sorted(npz.items()):
        W = np.asarray(val[1][0])
        b = np.asarray(val[1][1])
        print("  Loading %s: %s, %s" % (val[0], W.shape, b.shape))
        params.extend([W, b])
    tl.files.assign_params(sess, params, net_vgg)
    # net_vgg.print_params(False)
    # net_vgg.print_layers()

    ###============================= TRAINING ===============================###
    ## use first `batch_size` of train set to have a quick test during training
    sample_imgs = train_hr_imgs[0:batch_size]
    # sample_imgs = tl.vis.read_images(train_hr_img_list[0:batch_size], path=config.TRAIN.hr_img_path, n_threads=32) # if no pre-load train set
    
    print("sample_imgs size:", len(sample_imgs), sample_imgs[0].shape)
    
    sample_imgs_384 = tl.prepro.threading_data(sample_imgs, fn=crop_sub_imgs_fn, is_random=False)
    print('sample HR sub-image:', sample_imgs_384.shape, sample_imgs_384.min(), sample_imgs_384.max())
    sample_imgs_96 = tl.prepro.threading_data(sample_imgs_384, fn=downsample_fn)
    print('sample LR sub-image:', sample_imgs_96.shape, sample_imgs_96.min(), sample_imgs_96.max())
    tl.vis.save_images(sample_imgs_96, [ni, ni], save_dir_ginit + '/_train_sample_96.png')
    tl.vis.save_images(sample_imgs_384, [ni, ni], save_dir_ginit + '/_train_sample_384.png')
    tl.vis.save_images(sample_imgs_96, [ni, ni], save_dir_gan + '/_train_sample_96.png')
    tl.vis.save_images(sample_imgs_384, [ni, ni], save_dir_gan + '/_train_sample_384.png')

    ###========================= initialize G ====================###
    
    merged_summary_initial_G = tf.summary.merge([mse_loss_summary])
    summary_intial_G_writer = tf.summary.FileWriter("./log/train/initial_G")
    
    

    ## fixed learning rate
    sess.run(tf.assign(lr_v, lr_init))
    print(" ** fixed learning rate: %f (for init G)" % lr_init)
    count = 0
    for epoch in range(0, n_epoch_init + 1):
        epoch_time = time.time()
        total_mse_loss, n_iter = 0, 0

        ## If your machine cannot load all images into memory, you should use
        ## this one to load batch of images while training.
        # random.shuffle(train_hr_img_list)
        # for idx in range(0, len(train_hr_img_list), batch_size):
        #     step_time = time.time()
        #     b_imgs_list = train_hr_img_list[idx : idx + batch_size]
        #     b_imgs = tl.prepro.threading_data(b_imgs_list, fn=get_imgs_fn, path=config.TRAIN.hr_img_path)
        #     b_imgs_384 = tl.prepro.threading_data(b_imgs, fn=crop_sub_imgs_fn, is_random=True)
        #     b_imgs_96 = tl.prepro.threading_data(b_imgs_384, fn=downsample_fn)

        ## If your machine have enough memory, please pre-load the whole train set.
        
        
        intial_MSE_G_summary_per_epoch = []
        
        
        for idx in range(0, len(train_hr_imgs), batch_size):
            step_time = time.time()
            b_imgs_384 = tl.prepro.threading_data(train_hr_imgs[idx:idx + batch_size], fn=crop_sub_imgs_fn, is_random=True)
            b_imgs_96 = tl.prepro.threading_data(b_imgs_384, fn=downsample_fn)
            ## update G
            errM, _, mse_summary_initial_G = sess.run([mse_loss, g_optim_init, merged_summary_initial_G], {t_image: b_imgs_96, t_target_image: b_imgs_384})
            print("Epoch [%2d/%2d] %4d time: %4.4fs, mse: %.8f " % (epoch, n_epoch_init, n_iter, time.time() - step_time, errM))

            
            summary_pb = tf.summary.Summary()
            summary_pb.ParseFromString(mse_summary_initial_G)
            
            intial_G_summaries = {}
            for val in summary_pb.value:
            # Assuming all summaries are scalars.
                intial_G_summaries[val.tag] = val.simple_value
            #print("intial_G_summaries:", intial_G_summaries)
            
            
            intial_MSE_G_summary_per_epoch.append(intial_G_summaries['Generator_MSE_loss'])
            
            
            #summary_intial_G_writer.add_summary(mse_summary_initial_G, (count + 1)) #(epoch + 1)*(n_iter+1))
            #count += 1


            total_mse_loss += errM
            n_iter += 1
        log = "[*] Epoch: [%2d/%2d] time: %4.4fs, mse: %.8f" % (epoch, n_epoch_init, time.time() - epoch_time, total_mse_loss / n_iter)
        print(log)

        
        summary_intial_G_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Generator_Initial_MSE_loss per epoch", simple_value=np.mean(intial_MSE_G_summary_per_epoch)),]), (epoch))


        ## quick evaluation on train set
        #if (epoch != 0) and (epoch % 10 == 0):
        out = sess.run(net_g_test.outputs, {t_image: sample_imgs_96})  #; print('gen sub-image:', out.shape, out.min(), out.max())
        print("[*] save images")
        tl.vis.save_images(out, [ni, ni], save_dir_ginit + '/train_%d.png' % epoch)

        ## save model
        #if (epoch != 0) and (epoch % 10 == 0):
        tl.files.save_npz(net_g.all_params, name=checkpoint_dir + '/g_{}_{}_init.npz'.format(tl.global_flag['mode'], epoch), sess=sess)

    ###========================= train GAN (SRGAN) =========================###
    
    merged_summary_discriminator = tf.summary.merge([d_loss1_summary, d_loss2_summary, d_loss_summary])
    summary_discriminator_writer = tf.summary.FileWriter("./log/train/discriminator")
        
    merged_summary_generator = tf.summary.merge([g_gan_loss_summary, mse_loss_summary, vgg_loss_summary, g_loss_summary])
    summary_generator_writer = tf.summary.FileWriter("./log/train/generator")
    
    learning_rate_writer = tf.summary.FileWriter("./log/train/learning_rate")
    
    count = 0
    for epoch in range(0, n_epoch + 1):
        ## update learning rate
        if epoch != 0 and (epoch % decay_every == 0):
            new_lr_decay = lr_decay**(epoch // decay_every)
            sess.run(tf.assign(lr_v, lr_init * new_lr_decay))
            log = " ** new learning rate: %f (for GAN)" % (lr_init * new_lr_decay)
            print(log)


            learning_rate_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Learning_rate per epoch", simple_value=(lr_init * new_lr_decay)),]), (epoch))
            
            
        elif epoch == 0:
            sess.run(tf.assign(lr_v, lr_init))
            log = " ** init lr: %f  decay_every_init: %d, lr_decay: %f (for GAN)" % (lr_init, decay_every, lr_decay)
            print(log)


            learning_rate_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Learning_rate per epoch", simple_value=lr_init),]), (epoch))
            
            

        epoch_time = time.time()
        total_d_loss, total_g_loss, n_iter = 0, 0, 0

        
        
        ## If your machine cannot load all images into memory, you should use
        ## this one to load batch of images while training.
        # random.shuffle(train_hr_img_list)
        # for idx in range(0, len(train_hr_img_list), batch_size):
        #     step_time = time.time()
        #     b_imgs_list = train_hr_img_list[idx : idx + batch_size]
        #     b_imgs = tl.prepro.threading_data(b_imgs_list, fn=get_imgs_fn, path=config.TRAIN.hr_img_path)
        #     b_imgs_384 = tl.prepro.threading_data(b_imgs, fn=crop_sub_imgs_fn, is_random=True)
        #     b_imgs_96 = tl.prepro.threading_data(b_imgs_384, fn=downsample_fn)

        ## If your machine have enough memory, please pre-load the whole train set.
        
        loss_per_batch = []
        
        d_loss1_summary_per_epoch = []
        d_loss2_summary_per_epoch = []
        d_loss_summary_per_epoch = []
        
        
        g_gan_loss_summary_per_epoch = []
        mse_loss_summary_per_epoch = []
        vgg_loss_summary_per_epoch = []
        g_loss_summary_per_epoch = []
        
        
        for idx in range(0, len(train_hr_imgs), batch_size):
            step_time = time.time()
            b_imgs_384 = tl.prepro.threading_data(train_hr_imgs[idx:idx + batch_size], fn=crop_sub_imgs_fn, is_random=True)
            b_imgs_96 = tl.prepro.threading_data(b_imgs_384, fn=downsample_fn)
            ## update D
            errD, _, discriminator_summary = sess.run([d_loss, d_optim, merged_summary_discriminator], {t_image: b_imgs_96, t_target_image: b_imgs_384})
            
            
            summary_pb = tf.summary.Summary()
            summary_pb.ParseFromString(discriminator_summary)
            #print("discriminator_summary", summary_pb, type(summary_pb))
            
            discriminator_summaries = {}
            for val in summary_pb.value:
            # Assuming all summaries are scalars.
                discriminator_summaries[val.tag] = val.simple_value

            
            d_loss1_summary_per_epoch.append(discriminator_summaries['Disciminator_logits_real_loss'])
            d_loss2_summary_per_epoch.append(discriminator_summaries['Disciminator_logits_fake_loss'])
            d_loss_summary_per_epoch.append(discriminator_summaries['Disciminator_total_loss'])

            
            ## update G
            errG, errM, errV, errA, _, generator_summary = sess.run([g_loss, mse_loss, vgg_loss, g_gan_loss, g_optim, merged_summary_generator], {t_image: b_imgs_96, t_target_image: b_imgs_384})
            
            

            summary_pb = tf.summary.Summary()
            summary_pb.ParseFromString(generator_summary)
            #print("generator_summary", summary_pb, type(summary_pb))
            
            generator_summaries = {}
            for val in summary_pb.value:
            # Assuming all summaries are scalars.
                generator_summaries[val.tag] = val.simple_value

            #print("generator_summaries:", generator_summaries)    
            
            
            
            g_gan_loss_summary_per_epoch.append(generator_summaries['Generator_GAN_loss'])
            mse_loss_summary_per_epoch.append(generator_summaries['Generator_MSE_loss'])
            vgg_loss_summary_per_epoch.append(generator_summaries['Generator_VGG_loss'])
            g_loss_summary_per_epoch.append(generator_summaries['Generator_total_loss'])
            
            
            
            
            #summary_generator_writer.add_summary(generator_summary, (count + 1))
            
            #summary_total = sess.run(summary_total_merged, {t_image: b_imgs_96, t_target_image: b_imgs_384})
            #summary_total_merged_writer.add_summary(summary_total, (count + 1))
            
            #count += 1
            
            print("Epoch [%2d/%2d] %4d time: %4.4fs, d_loss: %.8f g_loss: %.8f (mse: %.6f vgg: %.6f adv: %.6f)" %
                  (epoch, n_epoch, n_iter, time.time() - step_time, errD, errG, errM, errV, errA))
            total_d_loss += errD
            total_g_loss += errG
            n_iter += 1

        log = "[*] Epoch: [%2d/%2d] time: %4.4fs, d_loss: %.8f g_loss: %.8f" % (epoch, n_epoch, time.time() - epoch_time, total_d_loss / n_iter,
                                                                                total_g_loss / n_iter)
        print(log)


        #####
        #
        # logging discriminator summary
        #
        ######

        # logging per epcoch summary of logit_real_loss per epoch. Value logged is averaged across batches used per epoch.
        summary_discriminator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Disciminator_logits_real_loss per epoch", simple_value=np.mean(d_loss1_summary_per_epoch)),]), (epoch))

        
        # logging per epcoch summary of logit_fake_loss per epoch. Value logged is averaged across batches used per epoch.
        summary_discriminator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Disciminator_logits_fake_loss per epoch", simple_value=np.mean(d_loss2_summary_per_epoch)),]), (epoch))


        # logging per epcoch summary of total_loss per epoch. Value logged is averaged across batches used per epoch.
        summary_discriminator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Disciminator_total_loss per epoch", simple_value=np.mean(d_loss_summary_per_epoch)),]), (epoch))

        

        
        #####
        #
        # logging generator summary
        #
        ######

        summary_generator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Generator_GAN_loss per epoch", simple_value=np.mean(g_gan_loss_summary_per_epoch)),]), (epoch))
        
        summary_generator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Generator_MSE_loss per epoch", simple_value=np.mean(mse_loss_summary_per_epoch)),]), (epoch))
        
        summary_generator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Generator_VGG_loss per epoch", simple_value=np.mean(vgg_loss_summary_per_epoch)),]), (epoch))
        
        summary_generator_writer.add_summary(tf.Summary(value=[tf.Summary.Value(tag="Generator_total_loss per epoch", simple_value=np.mean(g_loss_summary_per_epoch)),]), (epoch))
        
        
        
        
        ## quick evaluation on train set
        #if (epoch != 0) and (epoch % 10 == 0):
        out = sess.run(net_g_test.outputs, {t_image: sample_imgs_96})  #; print('gen sub-image:', out.shape, out.min(), out.max())
        print("[*] save images")
        tl.vis.save_images(out, [ni, ni], save_dir_gan + '/train_%d.png' % epoch)

        ## save model
        if (epoch != 0) and (epoch % 3 == 0):

        
            tl.files.save_npz(net_g.all_params, name=checkpoint_dir + '/g_{}_{}.npz'.format(tl.global_flag['mode'], epoch), sess=sess)
            tl.files.save_npz(net_d.all_params, name=checkpoint_dir + '/d_{}_{}.npz'.format(tl.global_flag['mode'], epoch), sess=sess)


def evaluate():
    ## create folders to save result images
    save_dir = "samples/{}".format(tl.global_flag['mode'])
    tl.files.exists_or_mkdir(save_dir)
    checkpoint_dir = "checkpoint"

    ###====================== PRE-LOAD DATA ===========================###
    # train_hr_img_list = sorted(tl.files.load_file_list(path=config.TRAIN.hr_img_path, regx='.*.png', printable=False))
    # train_lr_img_list = sorted(tl.files.load_file_list(path=config.TRAIN.lr_img_path, regx='.*.png', printable=False))
    valid_hr_img_list = sorted(tl.files.load_file_list(path=config.VALID.hr_img_path, regx='.*.png', printable=False))
    valid_lr_img_list = sorted(tl.files.load_file_list(path=config.VALID.lr_img_path, regx='.*.png', printable=False))

    ## If your machine have enough memory, please pre-load the whole train set.
    # train_hr_imgs = tl.vis.read_images(train_hr_img_list, path=config.TRAIN.hr_img_path, n_threads=32)
    # for im in train_hr_imgs:
    #     print(im.shape)
    
    #valid_lr_imgs = tl.vis.read_images(valid_lr_img_list, path=config.VALID.lr_img_path, n_threads=32)
    
    # for im in valid_lr_imgs:
    #     print(im.shape)
    
    #valid_hr_imgs = tl.vis.read_images(valid_hr_img_list, path=config.VALID.hr_img_path, n_threads=32)
    
    # for im in valid_hr_imgs:
    #     print(im.shape)
    # exit()

    
    valid_lr_imgs = []
    
    #sess = tf.Session()
    for img__ in valid_lr_img_list:
        
        
        image_loaded = scipy.misc.imread(os.path.join(config.VALID.lr_img_path, img__), mode='L')
        image_loaded = image_loaded.reshape((image_loaded.shape[0], image_loaded.shape[1], 1))

        valid_lr_imgs.append(image_loaded)
    
    print(type(valid_lr_imgs), len(valid_lr_img_list))
    
    
    
    valid_hr_imgs = []
    
    #sess = tf.Session()
    for img__ in valid_hr_img_list:
        
        
        image_loaded = scipy.misc.imread(os.path.join(config.VALID.hr_img_path, img__), mode='L')
        image_loaded = image_loaded.reshape((image_loaded.shape[0], image_loaded.shape[1], 1))

        valid_hr_imgs.append(image_loaded)
    
    print(type(valid_hr_imgs), len(valid_hr_img_list))
    
    
    
    
    
    ###========================== DEFINE MODEL ============================###
    imid = 1  # 0: ??????  81: ?????? 53: ???  64: ??????
    valid_lr_img = valid_lr_imgs[imid]
    valid_hr_img = valid_hr_imgs[imid]
    # valid_lr_img = get_imgs_fn('test.png', 'data2017/')  # if you want to test your own image
    valid_lr_img = (valid_lr_img / 127.5) - 1  # rescale to ??????1, 1]
    # print(valid_lr_img.min(), valid_lr_img.max())

    size = valid_lr_img.shape
    # t_image = tf.placeholder('float32', [None, size[0], size[1], size[2]], name='input_image') # the old version of TL need to specify the image size
 
    #t_image = tf.placeholder('float32', [1, None, None, 3], name='input_image')
    t_image = tf.placeholder('float32', [1, None, None, 1], name='input_image') # 1 for 1 channel

    net_g = SRGAN_g(t_image, is_train=False, reuse=False)

    ###========================== RESTORE G =============================###
    sess = tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False))
    tl.layers.initialize_global_variables(sess)
    tl.files.load_and_assign_npz(sess=sess, name=checkpoint_dir + '/g_srgan.npz', network=net_g)

    ###======================= EVALUATION =============================###
    start_time = time.time()
    out = sess.run(net_g.outputs, {t_image: [valid_lr_img]})
    print("took: %4.4fs" % (time.time() - start_time))

    print("LR size: %s /  generated HR size: %s" % (size, out.shape))  # LR size: (339, 510, 3) /  gen HR size: (1, 1356, 2040, 3)
    print("[*] save images")
    tl.vis.save_image(out[0], save_dir + '/valid_gen.png')
    tl.vis.save_image(valid_lr_img, save_dir + '/valid_lr.png')
    tl.vis.save_image(valid_hr_img, save_dir + '/valid_hr.png')

    valid_lr_img = valid_lr_img.reshape(valid_lr_img.shape[0], valid_lr_img.shape[1])
    out_bicu = scipy.misc.imresize(valid_lr_img, [size[0] * 4, size[1] * 4], interp='bicubic') #, mode=None)
    tl.vis.save_image(out_bicu, save_dir + '/valid_bicubic.png')
    
    hr_img_path = save_dir + '/valid_hr.png'
    bi_cubic_img_path = save_dir + '/valid_bicubic.png'
    gen_img_path = save_dir + '/valid_gen.png'

    bicubic_psnr = computePSNR(hr_img_path, bi_cubic_img_path)
    gen_psnr = computePSNR(hr_img_path, gen_img_path)

    print("Bicubic image PSNR:", bicubic_psnr)
    print("Generated image PSNR:", gen_psnr)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('--mode', type=str, default='srgan', help='srgan, evaluate')

    args = parser.parse_args()

    tl.global_flag['mode'] = args.mode

    if tl.global_flag['mode'] == 'srgan':
        train()
    elif tl.global_flag['mode'] == 'evaluate':
        evaluate()
    else:
        raise Exception("Unknow --mode")
