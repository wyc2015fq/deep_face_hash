try:
    import cPickle as pickle
except ImportError:
    import pickle

import itertools
import numpy as np

from data.img_utils import preprocess_images
from data.lfw_db import load_lfw_db, load_images
from data.storage import mongodb_store, mongodb_find, clear_collection
from bit_partition_lsh import generate_hash_maps, generate_hash_vars, calculate_mean_window_size
from vgg16 import generate_feature_maps, load_model
from utils import top_n_closer_vecs, top_n_closer_hash_codes, top_n_hamm_hash_codes


def hash_lfw(fpath='/home/aandronis/scikit_learn_data/lfw_home/lfw/', window=None, hash_size=None, reset_db=False,
             existing_maps=False):
    print("\n##################### INITIALIZE MODEL #########################")
    lfw_model = load_model()

    # compute one feature map to get dimensionality
    hash_vars = generate_hash_vars(model=lfw_model, bits=hash_size)

    # careful!!
    print("\n##################### DATABASE SETUP #########################")
    col_name = "_".join((str(window), str(hash_size), "bit"))
    feat_map_collection = "feature_maps"

    if reset_db:
        clear_collection(col_name)
    if not existing_maps:
        print("DELETED FEATURE MAPS COLLECTION! Re-preprocessing starting..")
        clear_collection('feature_maps')

    print("\n#################### CHUNK HANDLING ##########################")
    print("\nStarting Hashing...")

    (chunked_img_paths, chunked_targets, chunked_names, img_options) = load_lfw_db(fpath)
    if existing_maps:
        print("Using Preprocessed Feature Maps...")

        feature_maps = map(pickle.loads,
                           [item['feature_map'] for item in
                            mongodb_find({}, {'feature_map': 1}, None, collection=feat_map_collection)])
        hash_codes = generate_hash_maps(feature_maps, hash_vars, window, hash_size)
        targets = list(itertools.chain.from_iterable(chunked_targets))
        names = list(itertools.chain.from_iterable(chunked_names))
        batch_list = zip(hash_codes, targets, names)

        db_keys = ['hash_code', 'target', 'name']
        col_name = "_".join((str(window), str(hash_size), "bit"))
        mongodb_store(batch_list, db_keys, col_name)

        del (targets, names, hash_codes, feature_maps, batch_list)
    else:
        print("Total batches: " + str(img_options['n_batch']))
        print("Images per batch: " + str(img_options['num_faces']))

        batch_counter = 0
        for img_paths in chunked_img_paths:
            print("Starting image batch no." + str(batch_counter + 1) + "\n")
            print("Preprocessing Images...")

            preprocessed_images = preprocess_images(img_paths.tolist(), img_options=img_options)
            feature_maps = generate_feature_maps(preprocessed_images, lfw_model)
            hash_codes = generate_hash_maps(feature_maps, hash_vars, window, hash_size)
            batch_list = zip(hash_codes, chunked_targets[batch_counter].tolist(),
                             chunked_names[batch_counter].tolist())

            db_keys = ['hash_code', 'target', 'name']
            col_name = "_".join((str(window), str(hash_size), "bit"))
            mongodb_store(batch_list, db_keys, col_name)

            del (preprocessed_images, feature_maps, hash_codes, batch_list)

            print("\n##############################################")
            print("Finished image batch no." + str(batch_counter + 1))
            print("##############################################\n")

            batch_counter += 1

    del (chunked_img_paths, chunked_names, chunked_targets)

    print("\n##############################################")
    print("Finished creation of hashcodes")
    print("##############################################\n")

    return True


def deep_face_hashing(fpath, hash_size):
    print("\n##################### INITIALIZE MODEL #########################")
    lfw_model = load_model()

    # compute one feature map to get dimensionality
    hash_vars, window = generate_hash_vars(model=lfw_model, bits=hash_size)

    # careful!!
    print("\n##################### DATABASE SETUP #########################")
    col_name = "_".join((str(window), str(hash_size), "bit"))
    feat_map_collection = "feature_maps"

    img_paths = load_images(fpath)
    preprocessed_images = preprocess_images(img_paths, img_size=(250, 250))
    feature_maps = np.array(generate_feature_maps(preprocessed_images, lfw_model))
    hash_codes = generate_hash_maps(feature_maps, hash_vars, window, hash_size)
    names = np.array([item['name'] for item in mongodb_find({}, {'name': 1}, None, collection=col_name)])
    lfw_hash_maps = [item['hash_code'] for item in mongodb_find({}, {'hash_code': 1}, None, collection=col_name)]
    lfw_feat_maps = np.array(map(pickle.loads,
                                 [item['feature_map'] for item in
                                  mongodb_find({}, {'feature_map': 1}, None, collection=feat_map_collection)]))
    lfw_feat_maps = lfw_feat_maps.reshape(lfw_feat_maps.shape[0], lfw_feat_maps.shape[2])

    for hash_code in hash_codes:
        closest_indices = top_n_hamm_hash_codes(hash_code, lfw_hash_maps, 10)
        print("\nFor window size of: " + str(window) + " and hash size of: " + str(hash_size))
        print("\n Top 10 similar persons using hashmaps: ")
        for index in closest_indices:
            print(names[index])

    for feature_map in feature_maps:
        closest_indices = top_n_closer_vecs(lfw_feat_maps, feature_map, 10)
        print("\n Top 10 similar persons using feature map vectors: ")
        for index in closest_indices:
            print(names[index])

    return True


def generate_multiple_hash_map_collections():
    bit_sizes = [64, 128, 256, 512]

    for bits in bit_sizes:
        hash_lfw(window=calculate_mean_window_size(), hash_size=bits, reset_db=True, existing_maps=True)

    bit_sizes = [64, 128, 256, 512]
    for bits in bit_sizes:
        hash_lfw(window=calculate_mean_window_size()*2, hash_size=bits, reset_db=True, existing_maps=True)

    for window_size in range(100, 2000, 100):
        for bits in bit_sizes:
            hash_lfw(window=window_size, hash_size=bits, reset_db=True, existing_maps=True)


if __name__ == '__main__':
    # win_size = calculate_mean_window_size()
    # hash_lfw(window=win_size, hash_size=64, reset_db=False, existing_maps=True)
    # deep_face_hashing(fpath='/home/aandronis/projects/deep_face_hash/deep_face_hash/data/img/test/',
    #                   hash_size=512)
    generate_multiple_hash_map_collections()