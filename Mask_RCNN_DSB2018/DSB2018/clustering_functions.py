import pandas as pd                 
import numpy as np                                       
from sklearn.cluster import KMeans, DBSCAN
from scipy.ndimage.morphology import binary_fill_holes
import cv2                         # To read and manipulate images
import os                          # For filepath, directory handling
import sys                         # System-specific parameters and functions
import tqdm                        # Use smart progress meter
import matplotlib.pyplot as plt    # Python 2D plotting library
import matplotlib.cm as cm         # Color map
from sklearn.neighbors import NearestNeighbors

base_dir = 'D:/Kaggle/Data_Science_Bowl_2018' if os.name == 'nt' else os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
data_dir = os.path.join(base_dir, 'data')
train_dir = os.path.join(base_dir, 'train')
test_dir = os.path.join(base_dir, 'test') 
supplementary_data_dir = [os.path.join(base_dir, 'train_external', 'ISBI'),
                          os.path.join(base_dir, 'train_external', 'nsb')]
stage2_test_dir = os.path.join(base_dir, 'stage2_test_final') 


# Global constants.
IMG_DIR_NAME = 'images'   # Folder name including the image
MASK_DIR_NAME = 'masks'   # Folder name including the masks


# Collection of methods for data operations. Implemented are functions to read  
# images/masks from files and to read basic properties of the train/test data sets.

def read_image(filepath, color_mode=cv2.IMREAD_COLOR, target_size=None,space='bgr'):
    """Read an image from a file and resize it."""
    img = cv2.imread(filepath, color_mode)
    if target_size: 
        img = cv2.resize(img, target_size, interpolation = cv2.INTER_AREA)
    if space == 'hsv':
        img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return img

def resize_img(img, rows, cols):
    """
    Resize an image with cv2
    To shrink an image, it will generally look best with cv::INTER_AREA interpolation, whereas to enlarge an image, it will generally look best with cv::INTER_CUBIC (slow) or cv::INTER_LINEAR (faster but still looks OK).
    """
    interpolation = cv2.INTER_AREA if np.product(img.shape[:2]) > (rows * cols) else cv2.INTER_LINEAR
    return cv2.resize(img, (cols, rows), interpolation = interpolation)

def read_data_properties(source_dirs, img_dir_name):
    """Read basic properties of images."""

    tmp = []

    for _dir in source_dirs:

        for i, dir_name in enumerate(next(os.walk(_dir))[1]):

            img_dir = os.path.join(_dir, dir_name, img_dir_name)
            img_name = next(os.walk(img_dir))[2][0]
            img_name_id = os.path.splitext(img_name)[0]
            img_path = os.path.join(img_dir, img_name)
            img_shape = read_image(img_path).shape
            tmp.append(['{}'.format(img_name_id), img_shape[0], img_shape[1],
                        img_shape[0]/img_shape[1], img_shape[2], img_path])

    data_df = pd.DataFrame(tmp, columns = ['img_id', 'img_height', 'img_width',
                                           'img_ratio', 'num_channels', 'image_path'])

    return data_df

def load_raw_data(img_paths, image_size=(256, 256), space = 'bgr'):
    """Load raw data."""
    # Read and resize images. 
    print('Loading and resizing images ...')
    data = []
    sys.stdout.flush()
    for i, filename in tqdm.tqdm(enumerate(img_paths), total=len(img_paths)):
        img = read_image(filename, target_size=image_size, space=space)
        data.append(img)
    data = np.array(data)
    print('Data loaded')
    return data

def load_n_masks(img_paths):
    """LOAD NUMBER OF MASKS."""
    data = []
    for i, filename in tqdm.tqdm(enumerate(img_paths), total=len(img_paths)):
        mask_path = os.path.split(os.path.split(filename)[0])[0]
        masks = len(os.listdir(os.path.join(mask_path, MASK_DIR_NAME))) if os.path.exists(os.path.join(mask_path, MASK_DIR_NAME)) else -1
        data.append(masks)
    data = np.array(data)
    return data

def get_domimant_colors(img, top_colors=2):
    """Return dominant image color"""
    img_l = img.reshape((img.shape[0] * img.shape[1], img.shape[2]))
    clt = KMeans(n_clusters = top_colors)
    clt.fit(img_l)
    # grab the number of different clusters and create a histogram
    # based on the number of pixels assigned to each cluster
    numLabels = np.arange(0, len(np.unique(clt.labels_)) + 1)
    (hist, _) = np.histogram(clt.labels_, bins = numLabels)
    # normalize the histogram, such that it sums to one
    hist = hist.astype("float")
    hist /= hist.sum()
    return clt.cluster_centers_, hist

def cluster_images_by_hsv(img_paths, n_clusters=5, top_colors=2):
    """Clusterization based on hsv colors. Adds 'hsv_cluster' column to tables"""
    print('Loading data')
    x_hsv = load_raw_data(img_paths, image_size=(256,256), space='hsv')
    print('Calculating dominant hsv for each image')
    dominant_hsv = []
    for img in tqdm.tqdm(x_hsv):
        res1, res2 = get_domimant_colors(img,top_colors=top_colors)
        dominant_hsv.append(res1)
    dominant_hsv = np.array(dominant_hsv)
    dominant_hsv = dominant_hsv.reshape(dominant_hsv.shape[0], -1)
    print('Calculating clusters using KMeans')
    kmeans = KMeans(n_clusters=n_clusters, n_init=100, max_iter=500, random_state=0).fit(dominant_hsv)
    print('Images clustered')
    print('Calculating clusters using DBSCAN')
    dbscan = DBSCAN(eps=7).fit(dominant_hsv)
    print('Images clustered using DBSCAN')
    return kmeans.predict(dominant_hsv), dbscan.labels_

def plot_images(selected_images_df,images_rows=4,images_cols=8,plot_figsize=4):
    """Plot image_rows*image_cols of selected images. Used to visualy check clusterization"""
    f, axarr = plt.subplots(images_rows,images_cols,figsize=(plot_figsize*images_cols,images_rows*plot_figsize))
    for row in range(images_rows):
        for col in range(images_cols):
            if (row*images_cols + col) < selected_images_df.shape[0]:
                image_path = selected_images_df['image_path'].iloc[row*images_cols + col]
            else:
                continue
            img = read_image(image_path)
            height, width, l = img.shape
            ax = axarr[row,col]
            ax.axis('off')
            ax.set_title("%dx%d"%(width, height))
            ax.imshow(img)

def combine_images(data,indexes):
    """ Combines img from data using indexes as follows:
        0 1
        2 3 
    """
    up = np.hstack([data[indexes[0]],data[indexes[1]]])
    down = np.hstack([data[indexes[2]],data[indexes[3]]])
    full = np.vstack([up,down])
    return full

def make_mosaic(data,return_connectivity = False, plot_images = False,external_df = None):
    """Find images with simular borders and combine them to one big image"""
    if external_df is not None:
        external_df['mosaic_idx'] = np.nan
        external_df['mosaic_position'] = np.nan
        # print(external_df.head())
    
    # extract borders from images
    borders = []
    for x in data:
        borders.extend([x[0,:,:].flatten(),x[-1,:,:].flatten(),
                        x[:,0,:].flatten(),x[:,-1,:].flatten()])
    borders = np.array(borders)

    # prepare df with all data
    lens = np.array([len(border) for border in borders])
    img_idx = list(range(len(data)))*4
    img_idx.sort()
    position = ['up','down','left','right']*len(data)
    nn = [None]*len(position)
    df = pd.DataFrame(data=np.vstack([img_idx,position,borders,lens,nn]).T,
                      columns=['img_idx','position','border','len','nn'])
    uniq_lens = df['len'].unique()
    
    for idx,l in enumerate(uniq_lens):
        # fit NN on borders of certain size with 1 neighbor
        nn = NearestNeighbors(n_neighbors=1).fit(np.stack(df[df.len == l]['border'].values))
        distances, neighbors = nn.kneighbors()
        real_neighbor = np.array([None]*len(neighbors))
        distances, neighbors = distances.flatten(),neighbors.flatten()

        # if many borders are close to one, we want to take only the closest
        uniq_neighbors = np.unique(neighbors)

        # difficult to understand but works :c
        for un_n in uniq_neighbors:
            # min distance for borders with same nn
            min_index = list(distances).index(distances[neighbors == un_n].min())
            # check that min is double-sided
            double_sided = distances[neighbors[min_index]] == distances[neighbors == un_n].min()
            if double_sided and distances[neighbors[min_index]] < 1000:
                real_neighbor[min_index] = neighbors[min_index]
                real_neighbor[neighbors[min_index]] = min_index
        indexes = df[df.len == l].index
        for idx2,r_n in enumerate(real_neighbor):
            if r_n is not None:
                df['nn'].iloc[indexes[idx2]] = indexes[r_n]
    
    # img connectivity graph. 
    img_connectivity = {}
    for img in df.img_idx.unique():
        slc = df[df['img_idx'] == img]
        img_nn = {}

        # get near images_id & position
        for nn_border,position in zip(slc[slc['nn'].notnull()]['nn'],
                                      slc[slc['nn'].notnull()]['position']):

            # filter obvious errors when we try to connect bottom of one image to bottom of another
            # my hypotesis is that images were simply cut, without rotation
            if position == df.iloc[nn_border]['position']:
                continue
            img_nn[position] = df.iloc[nn_border]['img_idx']
        img_connectivity[img] = img_nn

    imgs = []
    indexes = set()
    mosaic_idx = 0
    
    # errors in connectivity are filtered 
    good_img_connectivity = {}
    for k,v in img_connectivity.items():
        if v.get('down') is not None:
            if v.get('right') is not None:
                # need down right image
                # check if both right and down image are connected to the same image in the down right corner
                if (img_connectivity[v['right']].get('down') is not None) and img_connectivity[v['down']].get('right') is not None:
                    if img_connectivity[v['right']]['down'] == img_connectivity[v['down']]['right']:
                        v['down_right'] = img_connectivity[v['right']]['down']
                        temp_indexes = [k,v['right'],v['down'],v['down_right']]
                        if (len(np.unique(temp_indexes)) < 4) or (len(indexes.intersection(temp_indexes)) > 0):
                            continue
                        good_img_connectivity[k] = temp_indexes
                        indexes.update(temp_indexes)
                        imgs.append(combine_images(data,temp_indexes))
                        if external_df is not None:
                            external_df['mosaic_idx'].iloc[temp_indexes] = mosaic_idx
                            external_df['mosaic_position'].iloc[temp_indexes] = ['up_left','up_right','down_left','down_right']
                            mosaic_idx += 1
                        continue
            if v.get('left') is not None:
                # need down left image
                if img_connectivity[v['left']].get('down') is not None and img_connectivity[v['down']].get('left') is not None:
                    if img_connectivity[v['left']]['down'] == img_connectivity[v['down']]['left']:
                        v['down_left'] = img_connectivity[v['left']]['down']
                        temp_indexes = [v['left'],k,v['down_left'],v['down']]
                        if (len(np.unique(temp_indexes)) < 4) or (len(indexes.intersection(temp_indexes)) > 0):
                            continue
                        good_img_connectivity[k] = temp_indexes
                        indexes.update(temp_indexes)
                        imgs.append(combine_images(data,temp_indexes))
                        
                        if external_df is not None:
                            external_df['mosaic_idx'].iloc[temp_indexes] = mosaic_idx
                            external_df['mosaic_position'].iloc[temp_indexes] = ['up_left','up_right','down_left','down_right']
                            
                            mosaic_idx += 1 
                        continue
        if v.get('up') is not None:
            if v.get('right') is not None:
                # need up right image
                if img_connectivity[v['right']].get('up') is not None and img_connectivity[v['up']].get('right') is not None:
                    if img_connectivity[v['right']]['up'] == img_connectivity[v['up']]['right']:
                        v['up_right'] = img_connectivity[v['right']]['up']
                        temp_indexes = [v['up'],v['up_right'],k,v['right']]
                        if (len(np.unique(temp_indexes)) < 4) or (len(indexes.intersection(temp_indexes)) > 0):
                            continue
                        good_img_connectivity[k] = temp_indexes
                        indexes.update(temp_indexes)
                        imgs.append(combine_images(data,temp_indexes))
                        
                        if external_df is not None:
                            external_df['mosaic_idx'].iloc[temp_indexes] = mosaic_idx
                            external_df['mosaic_position'].iloc[temp_indexes] = ['up_left','up_right','down_left','down_right']
                            
                            mosaic_idx += 1 
                        continue
            if v.get('left') is not None:
                # need up left image
                if img_connectivity[v['left']].get('up') is not None and img_connectivity[v['up']].get('left') is not None:
                    if img_connectivity[v['left']]['up'] == img_connectivity[v['up']]['left']:
                        v['up_left'] = img_connectivity[v['left']]['up']
                        temp_indexes = [v['up_left'],v['up'],v['left'],k]
                        if (len(np.unique(temp_indexes)) < 4) or (len(indexes.intersection(temp_indexes)) > 0):
                            continue
                        good_img_connectivity[k] = temp_indexes
                        indexes.update(temp_indexes)
                        imgs.append(combine_images(data,temp_indexes))
                        
                        if external_df is not None:
                            external_df['mosaic_idx'].iloc[temp_indexes] = mosaic_idx
                            external_df['mosaic_position'].iloc[temp_indexes] = ['up_left','up_right','down_left','down_right']
                            
                            mosaic_idx += 1 
                        continue

    # same images are present 4 times (one for every piece) so we need to filter them
    print('Images before filtering: {}'.format(np.shape(imgs)))
    
    # can use np. unique only on images of one size, flatten first, then select
    flattened = np.array([i.flatten() for i in imgs])
    uniq_lens = np.unique([i.shape for i in flattened])
    filtered_imgs = []
    for un_l in uniq_lens:
        filtered_imgs.extend(np.unique(np.array([i for i in imgs if i.flatten().shape == un_l]),axis=0))
        
    filtered_imgs = np.array(filtered_imgs)
    print('Images after filtering: {}'.format(np.shape(filtered_imgs)))
    
    if return_connectivity:
        print(good_img_connectivity)
    
    if plot_images:
        for i in filtered_imgs:
            plt.imshow(i)
            plt.show()
            
    # list of not combined images. return if you need
    not_combined = list(set(range(len(data))) - indexes)

    if external_df is not None:
        #un_mos_id = external_df[external_df.mosaic_idx.notnull()].mosaic_idx.unique()
        #mos_dict = {k:v for k,v in zip(un_mos_id,range(len(un_mos_id)))}
        #external_df.mosaic_idx = external_df.mosaic_idx.map(mos_dict)
        ## print(temp.mosaic_idx.shape[0])
        ## print(len(temp.mosaic_idx[temp.mosaic_idx.isnull()] ))
        ## print(len(list(range(temp.mosaic_idx.shape[0]-len(temp.mosaic_idx[temp.mosaic_idx.isnull()]),
        ##                     temp.mosaic_idx.shape[0]))))
        if np.all(external_df['mosaic_idx'].isnull()):
            external_df['mosaic_idx'] = range(1, 1 + len(external_df['mosaic_idx']))
        else:
            external_df.loc[external_df['mosaic_idx'].isnull(),'mosaic_idx'] = range(
                int(np.nanmax(external_df.mosaic_idx.unique())) + 1,
                int(np.nanmax(external_df.mosaic_idx.unique())) + 1 + len(external_df.mosaic_idx[external_df.mosaic_idx.isnull()]))
        external_df['mosaic_idx'] = external_df['mosaic_idx'].astype(np.int32)
        if return_connectivity:
            return filtered_imgs, external_df, good_img_connectivity
        else:
            return filtered_imgs, external_df
    if return_connectivity:
        return filtered_imgs,good_img_connectivity
    else:
        return filtered_imgs

def infer_target_id(imgs):
    """
    Returns id based on values of colour channels in img
    """
    """
    B = np.mean(imgs[:, :, :, 0], axis = (1, 2))
    G = np.mean(imgs[:, :, :, 1], axis = (1, 2)) 
    R = np.mean(imgs[:, :, :, 2], axis = (1, 2))
    Gray = np.mean(imgs, axis = (1, 2, 3))
    RB = R - B

    from sklearn.cluster import KMeans
    #kmeans = KMeans(n_clusters=3, random_state=0).fit(np.concatenate((R.reshape(-1, 1), G.reshape(-1, 1), B.reshape(-1, 1), Gray.reshape(-1, 1), RB.reshape(-1, 1)), axis = 1))
    kmeans = KMeans(n_clusters=2, random_state=0).fit(Gray.reshape(-1, 1))
       
    import visualisation as vis
    n = 25
    for vis_label in np.unique(kmeans.labels_):
        print(' '.join((str(vis_label), str(np.sum(kmeans.labels_ == vis_label)))))
        vis.plot_multiple_images([imgs[i] for i in np.argwhere(kmeans.labels_ == vis_label).reshape(-1, )[:n]], [str(vis_label)] * n, 5, 5)

    [np.min(gray[np.argwhere(kmeans.labels_ == 0)]), np.max(gray[np.argwhere(kmeans.labels_ == 0)])]
    [np.min(gray[np.argwhere(kmeans.labels_ == 1)]), np.max(gray[np.argwhere(kmeans.labels_ == 1)])]
    """
    gray = np.mean(imgs, axis = (1, 2, 3)) if imgs.ndim > 3 else np.mean(imgs, axis = (1, 2))

    colour_id = np.ones((len(imgs), ), dtype = np.int)
    colour_id[gray > 95] = 2

    return colour_id

def infer_maskcount_id(n_masks):
    """
    Returns id based on number of masks an image has
    """
    maskcount_id = np.zeros_like(n_masks)
    maskcount_id[np.logical_and(n_masks > 0, n_masks < 30)] = 1
    maskcount_id[np.logical_and(n_masks >= 30, n_masks < 100)] = 2
    maskcount_id[n_masks >= 100] = 3

    return maskcount_id

def run(save_filename, source_dirs=None, extra_dirs_for_clustering=None, run_hsv_clustering = False):

    if source_dirs is None:
        source_dirs = [train_dir] + [test_dir] + supplementary_data_dir

    # Basic properties of images/masks. 
    all_df = read_data_properties(source_dirs, IMG_DIR_NAME) 

    # Read images from files and resize them.
    x_all = load_raw_data(np.array(all_df['image_path']), image_size = None)
    x_n_masks = load_n_masks(np.array(all_df['image_path']))
    
    all_df['n_masks'] = x_n_masks

    # code which makes csv with clusters and mosaic ids for test data
    imgs, data_frame = make_mosaic(x_all, return_connectivity = False, plot_images = False, external_df = all_df)

    if extra_dirs_for_clustering is not None:
        extra_df = read_data_properties(extra_dirs_for_clustering, IMG_DIR_NAME)
        all_df_with_extra = pd.concat([all_df, extra_df])
    else:
        all_df_with_extra = all_df 
    
    if run_hsv_clustering:
        kmeans_cluster, dbscan_cluster = cluster_images_by_hsv(np.array(all_df_with_extra['image_path']), n_clusters=4, top_colors=1)
        all_df['cluster_id'], all_df['alt_cluster_id'] = kmeans_cluster[:len(all_df)], dbscan_cluster[:len(all_df)]
    else:
        all_df['cluster_id'] = np.zeros((all_df.shape[0],))
        all_df['alt_cluster_id'] = np.zeros((all_df.shape[0],))

    all_df['colour_id'] = infer_target_id(np.array([resize_img(x, 256, 256) for x in x_all]))

    all_df['maskcount_id'] = infer_maskcount_id(all_df['n_masks'])

    all_df.to_csv(save_filename, index = False)


def main():
    run()

if __name__ == '__main__':
    main()

