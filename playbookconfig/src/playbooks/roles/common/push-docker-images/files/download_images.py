#!/usr/bin/python
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from eventlet import greenpool
import docker
import sys
import time
import os
import json

MAX_DOWNLOAD_ATTEMPTS = 3
MAX_DOWNLOAD_THREAD = 5

DEFAULT_REGISTRIES = {
    'docker.io': 'docker.io',
    'gcr.io': 'gcr.io',
    'k8s.gcr.io': 'k8s.gcr.io',
    'quay.io': 'quay.io',
    'docker.elastic.co': 'docker.elastic.co'
}

registries = json.loads(os.environ['REGISTRIES'])


def download_an_image(img):
    # This function is to pull image from public/private
    # registry and push to local registry.
    #
    # Examples of passed img reference:
    #  - k8s.gcr.io/kube-proxy:v.16.0
    #  - privateregistry.io:5000/kube-proxy:v1.16.0
    #
    # To push to local registry, local registry url
    # 'registry.local:9001' needs to be prepended to
    # image reference. The registry url of passed img
    # may contains a port, if it has a port, we strip
    # it out as Docker does not allow the format of
    # the image that has port in repositories/namespaces
    # i.e.
    # Invalid format:
    #   registry.local:9001/privateregistry.io:5000/kube-proxy:v1.16.0
    registry_url = img[:img.find('/')]
    if ':' in registry_url:
        img_name = img[img.find('/'):]
        new_img = registry_url.split(':')[0] + img_name
    else:
        new_img = img

    target_img = get_img_tag_with_registry(img)
    local_img = 'registry.local:9001/' + new_img
    err_msg = " Image download failed: %s" % target_img

    for i in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            client = docker.APIClient()
            client.pull(target_img)
            client.tag(target_img, local_img)
            client.push(local_img)
            print("Image download succeeded: %s" % target_img)
            print("Image push succeeded: %s" % local_img)
            return target_img, True
        except docker.errors.NotFound as e:
            print(err_msg + str(e))
            return target_img, False
        except docker.errors.APIError as e:
            print(err_msg + str(e))
            if "no basic auth credentials" in str(e):
                return target_img, False
        except Exception as e:
            print(err_msg + str(e))

        print("Sleep 20s before retry downloading image %s ..." % target_img)
        time.sleep(20)

    return target_img, False


def get_img_tag_with_registry(pub_img):
    if registries == DEFAULT_REGISTRIES:
        # return as no private registires configured
        return pub_img

    for registry_default, registry_replaced in registries.items():
        if pub_img.startswith(registry_default):
            img_name = pub_img.split(registry_default)[1]
            return registry_replaced + img_name
        elif pub_img.startswith(registry_replaced):
            return pub_img

    # If the image is not from any of the known registries
    # (ie..k8s.gcr.io, gcr.io, quay.io, docker.io. docker.elastic.co)
    # or no registry name specified in image tag, use user specified
    # docker registry as default
    if registries['docker.io'] != DEFAULT_REGISTRIES['docker.io']:
        return registries['docker.io'] + '/' + pub_img
    return pub_img


def download_images(images):
    failed_images = []
    threads = min(MAX_DOWNLOAD_THREAD, len(images))

    pool = greenpool.GreenPool(size=threads)
    for img, success in pool.imap(download_an_image, images):
        if not success:
            failed_images.append(img)
    return failed_images


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise Exception("Invalid Input!")

    image_list = sys.argv[1].split(',')

    start = time.time()
    failed_downloads = download_images(image_list)
    elapsed_time = time.time() - start

    if len(failed_downloads) > 0:
        raise Exception("Failed to download images %s" % failed_downloads)
    else:
        print("All images downloaded and pushed to the local "
              "registry in %s seconds" % elapsed_time)
