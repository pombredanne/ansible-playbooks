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

MAX_DOWNLOAD_ATTEMPTS = 3
MAX_DOWNLOAD_THREAD = 5


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

    local_img = 'registry.local:9001/' + new_img
    err_msg = " Image %s download failed: " % img

    for i in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            client = docker.APIClient()
            client.pull(img)
            client.tag(img, local_img)
            client.push(local_img)
            print("Image %s download succeeded" % img)
            return img, True
        except docker.errors.NotFound as e:
            print(err_msg + str(e))
            return img, False
        except docker.errors.APIError as e:
            print(err_msg + str(e))
            if "no basic auth credentials" in str(e):
                return img, False
        except Exception as e:
            print(err_msg + str(e))

        print("Sleep 20s before retry downloading image %s ..." % img)
        time.sleep(20)

    return img, False


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
