# 2015.10.09 12:02:45 EDT
# Embedded file name: /home/karim/Documents/pasca/packages/neuropype_ephy/neuropype_ephy/compute_inv_problem.py
"""
Created on Thu Oct  8 17:53:07 2015

@author: pasca
"""


# compute noise covariance data from a continuous segment of raw data.
# Employ empty room data (collected without the subject) to calculate the full noise covariance matrix. 
# This is recommended for analyzing ongoing spontaneous activity. 
def compute_noise_cov(cov_fname, raw):
    import os.path as op
    import numpy as np
    
    from mne import compute_raw_covariance, pick_types, write_cov, read_cov
    from nipype.utils.filemanip import split_filename as split_f
    
    print '***** COMPUTE RAW COV *****' + cov_fname
    
    if not op.isfile(cov_fname):    
        
        data_path, basename, ext = split_f(raw.info['filename'])
        fname = op.join(data_path, '%s-cov.fif' % basename)
                
        reject = dict(mag=4e-12, grad=4000e-13, eog=250e-6)
    
        picks = pick_types(raw.info, meg=True, ref_meg=False, exclude='bads')
        
        noise_cov = compute_raw_covariance(raw, picks=picks, reject=reject)

        write_cov(fname, noise_cov)
        
    else:
        print '*** NOISE cov file %s exists!!!' % cov_fname
#        noise_cov = read_cov(cov_fname)
    
#    return noise_cov
    return cov_fname
    
def read_noise_cov(cov_fname, raw_info):
    import os.path as op
    import numpy as np
    import mne    

    print '***** READ RAW COV *****' + cov_fname
   
    if not op.isfile(cov_fname):    
        # create an Identity matrix
        picks = mne.pick_types(raw_info, meg=True, ref_meg=False, exclude='bads')
        ch_names=[raw_info['ch_names'][i] for i in picks]

        C = mne.Covariance(data=np.identity(len(picks)), names=ch_names, bads = [], projs=[], nfree=0)
        mne.write_cov(cov_fname, C)
    else:
        print '*** noise covariance file %s exists!!!' % cov_fname
        noise_cov = mne.read_cov(cov_fname)
    
    return noise_cov

# compute inverse solution on raw data
def compute_inv_sol(raw, fwd_filename, cov_fname, snr, inv_method, aseg):
    import os.path as op
    import numpy as np
    import mne
    from mne.minimum_norm import make_inverse_operator, apply_inverse_raw
    from nipype.utils.filemanip import split_filename as split_f
    
    print '***** READ FWD SOL %s *****' %fwd_filename
    forward = mne.read_forward_solution(fwd_filename)
    
    # Convert to surface orientation for cortically constrained inverse modeling
    if not aseg:
        forward = mne.convert_forward_solution(forward, surf_ori=True)

    lambda2 = 1.0 / snr ** 2
    
    # compute inverse operator    
    print '***** COMPUTE INV OP *****'
    inverse_operator = make_inverse_operator(raw.info, forward, noise_cov, 
                                             loose=0.2, depth=0.8)
    
    # apply inverse operator to the time windows [t_start, t_stop]s
    # TEST
    t_start = 0 # sec
    t_stop  = 3 # sec
    start, stop = raw.time_as_index([t_start, t_stop])
    print '***** APPLY INV OP ***** [%d %d]sec' %(t_start, t_stop)
    stc = apply_inverse_raw(raw, inverse_operator, lambda2, inv_method, label=None, 
                            start=start, stop=stop, pick_ori=None)
    
    print '***'
    print 'stc dim ' + str(stc.shape)
    print '***'
    
    subj_path, basename, ext = split_f(raw.info['filename'])
    data = stc.data
    
    print 'data dim ' + str(data.shape)

    # save results in .npy file that will be the input for spectral node
    print '***** SAVE SOL *****'
    ts_file = op.abspath(basename + '.npy')
    np.save(ts_file, data)

    return ts_file
    
# compute the inverse solution on raw data considering N_r regions in source space 
# based on a FreeSurfer cortical parcellation
def compute_ROIs_inv_sol(raw, sbj_id, sbj_dir, fwd_filename, cov_fname, snr, inv_method, parc, aseg):
    import os.path as op
    import numpy as np
    import mne
    from mne.minimum_norm import make_inverse_operator, apply_inverse_raw
    from nipype.utils.filemanip import split_filename as split_f
     
    print '***** READ noise covariance %s *****' % cov_fname
    noise_cov = mne.read_cov(cov_fname)
    
    print '***** READ FWD SOL %s *****' %fwd_filename
    forward = mne.read_forward_solution(fwd_filename)
    
    if not aseg:
        forward = mne.convert_forward_solution(forward, surf_ori=True)

    lambda2 = 1.0 / snr ** 2
    
    # compute inverse operator    
    print '***** COMPUTE INV OP *****'    
    inverse_operator = make_inverse_operator(raw.info, forward, noise_cov, loose=0.2, depth=0.8)
 
    # apply inverse operator to the time windows [t_start, t_stop]s
    print '***** APPLY INV OP *****' 
    stc = apply_inverse_raw(raw, inverse_operator, lambda2, inv_method, label=None, 
                            start=None, stop=None, buffer_size = 1000, 
                            pick_ori=None) #None 'normal'
    
    print '***'
    print 'stc dim ' + str(stc.shape)
    print '***'
    
    labels = mne.read_labels_from_annot(sbj_id, parc=parc,
                                        subjects_dir=sbj_dir)
    
    src = inverse_operator['src']
    label_ts = mne.extract_label_time_course(stc, labels, src, mode='mean_flip',
                                             return_generator=True)

    # save results in .npy file that will be the input for spectral node
    print '***** SAVE SOL *****'
    subj_path, basename, ext = split_f(raw.info['filename'])    
    ts_file = op.abspath(basename + '.npy')
    np.save(ts_file, label_ts)

    return ts_file, labels