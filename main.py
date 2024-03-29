import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow.keras.backend as K
import random
from PIL import Image
# from scipy.misc import imresize
from scipy.optimize import fmin_l_bfgs_b   # https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.fmin_l_bfgs_b.html
from tensorflow.keras.applications import vgg19
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import warnings


random.seed(1618)
np.random.seed(1618)
#tf.set_random_seed(1618)   # Uncomment for TF1.
tf.random.set_seed(1618)

#tf.logging.set_verbosity(tf.logging.ERROR)   # Uncomment for TF1.
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.compat.v1.disable_eager_execution()
CONTENT_IMG_PATH = "./content_img.jpg"
STYLE_IMG_PATH = "./style_img.jpg"


CONTENT_IMG_H = 500
CONTENT_IMG_W = 500

STYLE_IMG_H = 500
STYLE_IMG_W = 500

CONTENT_WEIGHT = .0001    # Alpha weight.
STYLE_WEIGHT = 1      # Beta weight.
TOTAL_WEIGHT = 1.0

TRANSFER_ROUNDS = 3



#=============================<Helper Fuctions>=================================
'''
This function should take the tensor and re-convert it to an image.
'''
def deprocessImage(img):
    img = img.reshape(CONTENT_IMG_H,CONTENT_IMG_W,3)
    img[:, :, 0] += 103.939
    img[:, :, 1] += 116.779
    img[:, :, 2] += 123.68
    img = img[:, :, ::-1]
    img = np.clip(img, 0, 255).astype('uint8')
    return Image.fromarray(img)


def gramMatrix(x):
    features = K.batch_flatten(K.permute_dimensions(x, (2, 0, 1)))
    gram = K.dot(features, K.transpose(features))
    return gram



#========================<Loss Function Builder Functions>======================

def styleLoss(style, gen):
    numFilters = 3
    gram_s = gramMatrix(style)
    gram_g = gramMatrix(gen)
    num = K.sum(K.square(gram_s-gram_g))
    den = (4*(numFilters**2)*(STYLE_IMG_H*STYLE_IMG_W)**2)
    return num/den


def contentLoss(content, gen):
    return K.sum(K.square(gen - content))


#=========================<Pipeline Functions>==================================

def getRawData():
    print("   Loading images.")
    print("      Content image URL:  \"%s\"." % CONTENT_IMG_PATH)
    print("      Style image URL:    \"%s\"." % STYLE_IMG_PATH)
    cImg = load_img(CONTENT_IMG_PATH)
    tImg = cImg.copy()
    sImg = load_img(STYLE_IMG_PATH)
    print("      Images have been loaded.")
    return ((cImg, CONTENT_IMG_H, CONTENT_IMG_W), (sImg, STYLE_IMG_H, STYLE_IMG_W), (tImg, CONTENT_IMG_H, CONTENT_IMG_W))



def preprocessData(raw):
    img, ih, iw = raw
    img = img_to_array(img, dtype=np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        img = np.array(Image.fromarray(img).resize((ih,iw)))
        # img = imresize(img, (ih, iw, 3))
    img = img.astype("float64")
    img = np.expand_dims(img, axis=0)
    img = vgg19.preprocess_input(img)
    return img


'''
First, make sure the model is set up properly.
Then construct the loss function (from content and style loss).
Gradient functions will also need to be created, or you can use K.Gradients().
Finally, do the style transfer with gradient descent.
Save the newly generated and deprocessed images.
'''
def styleTransfer(cData, sData, tData):
    print("   Building transfer model.")
    tData = tData.flatten()
    contentTensor = K.variable(cData)
    styleTensor = K.variable(sData)
    genTensor = K.placeholder((1, CONTENT_IMG_H, CONTENT_IMG_W, 3))
    inputTensor = K.concatenate([contentTensor, styleTensor, genTensor], axis=0)
    model = vgg19.VGG19(include_top=False,weights='imagenet',input_tensor=inputTensor)
    outputDict = dict([(layer.name, layer.output) for layer in model.layers])
    print("   VGG19 model loaded.")
    styleLayerNames = ["block1_conv1", "block2_conv1", "block3_conv1", "block4_conv1", "block5_conv1"]
    contentLayerName = "block5_conv2"
    
    print("   Calculating content loss.")
    contentLayer = outputDict[contentLayerName]
    contentOutput = contentLayer[0, :, :, :]
    genOutput = contentLayer[2, :, :, :]
    content_loss = contentLoss(contentOutput, genOutput)
    
    print("   Calculating style loss.")
    style_loss = 0
    for layerName in styleLayerNames:
        styleLayer = outputDict[layerName]
        styleOutput = styleLayer[1,:,:,:]
        genOutput = styleLayer[2,:,:,:]
        l_w = STYLE_WEIGHT/len(styleLayerNames)
        style_loss += l_w * styleLoss(styleOutput,genOutput)
    loss = CONTENT_WEIGHT*content_loss + STYLE_WEIGHT*style_loss 
    grad = K.gradients(loss,genTensor)[0]
    
    outputs = [loss]
    outputs.append(grad)
    kFunction = K.function([genTensor],outputs)
    print("   Beginning transfer.")
    def loss_f(x):
        x = x.reshape((1, CONTENT_IMG_H,CONTENT_IMG_W, 3))
        outs = kFunction([x])
        loss_value = outs[0]
        return loss_value
    
    def grads_f(x):
        x = x.reshape((1, CONTENT_IMG_H,CONTENT_IMG_W, 3))
        outs = kFunction([x])
        grad_values = outs[1].flatten().astype('float64')
        return grad_values
    for i in range(TRANSFER_ROUNDS):
        print("   Step %d." % i)
        x,tLoss,info = fmin_l_bfgs_b(loss_f,tData,grads_f,maxiter=200)
        print("      Loss: %f." % tLoss)
        img = deprocessImage(x)
        path = "output"+str(i)+".png"
        img.save(path)
        print("      Image saved to \"%s\"." % path)
    print("   Transfer complete.")





#=========================<Main>================================================

def main():
    print("Starting style transfer program.")
    raw = getRawData()
    cData = preprocessData(raw[0])   # Content image.
    sData = preprocessData(raw[1])   # Style image.
    tData = preprocessData(raw[2])   # Transfer image.
    styleTransfer(cData, sData, tData)
    print("Done. Goodbye.")



if __name__ == "__main__":
    main()