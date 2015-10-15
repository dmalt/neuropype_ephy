# -*- coding: utf-8 -*-

def preprocess_fif_to_ts(fif_file, l_freq, h_freq, down_sfreq):

	import os
	import numpy as np

	from mne.io import Raw	
	#from mne.io import RawFIF	## was working in previous versions ofpyMNE
	from nipype.utils.filemanip import split_filename as split_f

	subj_path,basename,ext = split_f(fif_file)

	print fif_file
	
	raw = Raw(fif_file,preload = True)

	print raw

	print len(raw.ch_names)

	select_sensors, = np.where(np.array([ch_name[0] == 'M' for ch_name in raw.ch_names],dtype = 'bool') == True)

	### save electrode locations
	sens_loc = [raw.info['chs'][i]['loc'][:3] for i in select_sensors]
	sens_loc = np.array(sens_loc)

	channel_coords_file = os.path.abspath("correct_channel_coords.txt")
	np.savetxt(channel_coords_file ,sens_loc , fmt = '%s')

	# print sens_loc

	### save electrode names
	sens_names = np.array([raw.ch_names[pos] for pos in select_sensors],dtype = "str")

	channel_names_file = os.path.abspath("correct_channel_names.txt")
	np.savetxt(channel_names_file,sens_names , fmt = '%s')

	### filtering + downsampling

	data,times = raw[select_sensors,:]
	print data.shape
	print raw.info['sfreq']

	raw.filter(l_freq = None, h_freq = h_freq,picks = select_sensors)

	raw.resample(sfreq = down_sfreq,npad = 0,stim_picks = select_sensors)


	### save data
	data,times = raw[select_sensors,:]
	print data.shape
	print raw.info['sfreq']
	#0/0


	ts_file = os.path.abspath(basename +".npy")

	np.save(ts_file,data)

	return ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']

def preprocess_ICA_fif_to_ts(fif_file, ECG_ch_name, EoG_ch_name, l_freq, h_freq, down_sfreq, is_sensor_space):
    import os
    import numpy as np

    import mne
    from mne.io import Raw	
    from mne.preprocessing import ICA, read_ica
    from mne.preprocessing import create_ecg_epochs, create_eog_epochs
    from mne.report import Report

    from nipype.utils.filemanip import split_filename as split_f
    
    report = Report()

    subj_path,basename,ext = split_f(fif_file)
    
    ### Read raw
    #   If None the compensation in the data is not modified. If set to n, e.g. 3, apply   
    #   gradient compensation of grade n as for CTF systems (compensation=3)
    raw = Raw(fif_file, preload=True)

    ### select sensors                                         
    select_sensors = mne.pick_types(raw.info, meg=True, ref_meg= False, exclude='bads')
    picks_meeg     = mne.pick_types(raw.info, meg=True, eeg=True, exclude='bads')
    
    ### save electrode locations
    sens_loc = [raw.info['chs'][i]['loc'][:3] for i in select_sensors]
    sens_loc = np.array(sens_loc)

    channel_coords_file = os.path.abspath("correct_channel_coords.txt")
    np.savetxt(channel_coords_file ,sens_loc , fmt = '%s')

    ### save electrode names
    sens_names = np.array([raw.ch_names[pos] for pos in select_sensors],dtype = "str")

    channel_names_file = os.path.abspath("correct_channel_names.txt")
    np.savetxt(channel_names_file,sens_names , fmt = '%s')
 
    ### filtering + downsampling
    raw.filter(l_freq = l_freq, h_freq = h_freq, picks = picks_meeg, method='iir', n_jobs=2)
    raw.resample(sfreq = down_sfreq, npad = 0)


    ### 1) Fit ICA model using the FastICA algorithm
    # Other available choices are `infomax` or `extended-infomax`
    # We pass a float value between 0 and 1 to select n_components based on the
    # percentage of variance explained by the PCA components.
    ICA_title = 'Sources related to %s artifacts (red)'
    is_show = False # visualization
    reject = dict(mag=4e-12, grad=4000e-13)

    # check if we have an ICA, if yes, we load it
    ica_filename = os.path.join(subj_path,basename + "-ica.fif")  
    if os.path.exists(ica_filename) == False:
        ica = ICA(n_components=0.95, method='fastica') # , max_iter=500
        ica.fit(raw, picks=select_sensors, reject=reject) # decim = 3, 
        
        has_ICA = False
    else:
        has_ICA = True
        ica = read_ica(ica_filename)
        ica.exclude = [] 

    ### 2) identify bad components by analyzing latent sources.
    # generate ECG epochs use detection via phase statistics
    
    # if we just have exclude channels we jump these steps
#    if len(ica.exclude)==0:
    n_max_ecg = 3
    n_max_eog = 2
    
    # check if ECG_ch_name is in the raw channels
    if ECG_ch_name in raw.info['ch_names']:
        ecg_epochs = create_ecg_epochs(raw, tmin=-.5, tmax=.5, picks=select_sensors, 
                                       ch_name = ECG_ch_name)
    # if not  a synthetic ECG channel is created from cross channel average
    else:
        ecg_epochs = create_ecg_epochs(raw, tmin=-.5, tmax=.5, picks=select_sensors)
    
    ### ICA for ECG artifact 
    # threshold=0.25 come defualt
    ecg_inds, scores = ica.find_bads_ecg(ecg_epochs, method='ctps')
    if len(ecg_inds) > 0:
        ecg_evoked = ecg_epochs.average()
        
        fig1 = ica.plot_scores(scores, exclude=ecg_inds, title=ICA_title % 'ecg', show=is_show)

        show_picks = np.abs(scores).argsort()[::-1][:5] # Pick the five largest scores and plot them

        # Plot estimated latent sources given the unmixing matrix.
        #ica.plot_sources(raw, show_picks, exclude=ecg_inds, title=ICA_title % 'ecg', show=is_show)
#            t_start, t_stop = raw.time_as_index([0, 30]) # take the fist 30s
        t_start = 0
        t_stop = 30 # take the fist 30s
        fig2 = ica.plot_sources(raw, show_picks, exclude=ecg_inds, title=ICA_title % 'ecg' + ' in 30s' 
                                            ,start = t_start, stop  = t_stop, show=is_show)

        # topoplot of unmixing matrix columns
        fig3 = ica.plot_components(show_picks, title=ICA_title % 'ecg', colorbar=True, show=is_show)

        ecg_inds = ecg_inds[:n_max_ecg]
        ica.exclude += ecg_inds
    
        fig4 = ica.plot_sources(ecg_evoked, exclude=ecg_inds, show=is_show)  # plot ECG sources + selection
        fig5 = ica.plot_overlay(ecg_evoked, exclude=ecg_inds, show=is_show)  # plot ECG cleaning
    
        fig = [fig1, fig2, fig3, fig4, fig5]
        report.add_figs_to_section(fig, captions=['Scores of ICs related to ECG',
                                                  'Time Series plots of ICs (ECG)',
                                                  'TopoMap of ICs (ECG)', 
                                                  'Time-locked ECG sources', 
                                                  'ECG overlay'], section = 'ICA - ECG')    
    
    # check if EoG_ch_name is in the raw channels
    if EoG_ch_name in raw.info['ch_names']:        
        ### ICA for eye blink artifact - detect EOG by correlation
        eog_inds, scores = ica.find_bads_eog(raw, ch_name = EoG_ch_name)
    else:
        eog_inds, scores = ica.find_bads_eog(raw)

    if len(eog_inds) > 0:  
        
        fig6 = ica.plot_scores(scores, exclude=eog_inds, title=ICA_title % 'eog', show=is_show)
        report.add_figs_to_section(fig6, captions=['Scores of ICs related to EOG'], 
                           section = 'ICA - EOG')
                           
        # check how many EoG ch we have
        rs = np.shape(scores)
        if len(rs)>1:
            rr = rs[0]
            show_picks = [np.abs(scores[i][:]).argsort()[::-1][:5] for i in range(rr)]
            for i in range(rr):
                fig7 = ica.plot_sources(raw, show_picks[i][:], exclude=eog_inds, 
                                    start = raw.times[0], stop  = raw.times[-1], 
                                    title=ICA_title % 'eog',show=is_show)       
                                    
                fig8 = ica.plot_components(show_picks[i][:], title=ICA_title % 'eog', colorbar=True, show=is_show) # ICA nel tempo

                fig = [fig7, fig8]
                report.add_figs_to_section(fig, captions=['Scores of ICs related to EOG', 
                                                 'Time Series plots of ICs (EOG)'],
                                            section = 'ICA - EOG')    
        else:
            show_picks = np.abs(scores).argsort()[::-1][:5]
            fig7 = ica.plot_sources(raw, show_picks, exclude=eog_inds, title=ICA_title % 'eog', show=is_show)                                    
            fig8 = ica.plot_components(show_picks, title=ICA_title % 'eog', colorbar=True, show=is_show) 
            fig = [fig7, fig8]            
            report.add_figs_to_section(fig, captions=['Time Series plots of ICs (EOG)',
                                                      'TopoMap of ICs (EOG)',],
                                            section = 'ICA - EOG') 
        
        eog_inds = eog_inds[:n_max_eog]
        ica.exclude += eog_inds
        
        if EoG_ch_name in raw.info['ch_names']:
            eog_evoked = create_eog_epochs(raw, tmin=-.5, tmax=.5, picks=select_sensors, 
                                   ch_name=EoG_ch_name).average()
        else:
            eog_evoked = create_eog_epochs(raw, tmin=-.5, tmax=.5, picks=select_sensors).average()               
       
        fig9 = ica.plot_sources(eog_evoked, exclude=eog_inds, show=is_show)  # plot EOG sources + selection
        fig10 = ica.plot_overlay(eog_evoked, exclude=eog_inds, show=is_show)  # plot EOG cleaning

        fig = [fig9, fig10]
        report.add_figs_to_section(fig, captions=['Time-locked EOG sources',
                                                  'EOG overlay'], section = 'ICA - EOG')

    fig11 = ica.plot_overlay(raw, show=is_show)
    report.add_figs_to_section(fig11, captions=['Signal'], section = 'Signal quality') 
    report_filename = os.path.join(subj_path,basename + "-report.html")
    print '******* ' + report_filename
    report.save(report_filename, open_browser=False, overwrite=True)
        
        
    ### 3) apply ICA to raw data and save solution and report
    # check the amplitudes do not change
    raw_ica = ica.apply(raw, copy=True)

    ### save ICA solution  
    print ica_filename
    if has_ICA == False:
        ica.save(ica_filename)

    ### 4) save data
    data_noIca,times = raw[select_sensors,:]
    data,times       = raw_ica[select_sensors,:]

    print data.shape
    print raw.info['sfreq']

    ts_file = os.path.abspath(basename +"_ica.npy")
    np.save(ts_file,data)

    if is_sensor_space:
        return ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']
    else:
        return raw_ica, ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']


# load ICA and set components we want to exclude
def preprocess_set_ICA_comp_fif_to_ts(fif_file, n_comp_exclude, l_freq, h_freq, down_sfreq, is_sensor_space):
    import os
    import numpy as np
    import sys

    import mne
    from mne.io import Raw	
    from mne.preprocessing import read_ica
    from mne.report import Report

    from nipype.utils.filemanip import split_filename as split_f
    
    report = Report()

    subj_path,basename,ext = split_f(fif_file)
    
    ### Read raw
    raw = Raw(fif_file, preload=True)

    ### select sensors                                         
    select_sensors = mne.pick_types(raw.info, meg=True, ref_meg= False, exclude='bads')
    picks_meeg     = mne.pick_types(raw.info, meg=True, eeg=True, exclude='bads')
    
    ### save electrode locations
    sens_loc = [raw.info['chs'][i]['loc'][:3] for i in select_sensors]
    sens_loc = np.array(sens_loc)

    channel_coords_file = os.path.abspath("correct_channel_coords.txt")
    np.savetxt(channel_coords_file ,sens_loc , fmt = '%s')

    ### save electrode names
    sens_names = np.array([raw.ch_names[pos] for pos in select_sensors],dtype = "str")

    channel_names_file = os.path.abspath("correct_channel_names.txt")
    np.savetxt(channel_names_file,sens_names , fmt = '%s')
 
    ### filtering + downsampling
    raw.filter(l_freq = l_freq, h_freq = h_freq, picks = picks_meeg, method='iir', n_jobs=2)
    raw.resample(sfreq = down_sfreq, npad = 0)

    

    ### load ICA
    is_show = False # visualization
    ica_filename = os.path.join(subj_path,basename + "-ica.fif")  
    if os.path.exists(ica_filename) == False:
        print "$$$$$$$$$$$$$ Warning, no %s found" %ica_filename
        
        sys.exit() 

    else:
        ica = read_ica(ica_filename)
        
    print '***** ica.exclude = ', ica.exclude
    ica.exclude = n_comp_exclude
    print '***** ica.exclude after = ', ica.exclude
    
    fig1 = ica.plot_overlay(raw, show=is_show)
    report.add_figs_to_section(fig1, captions=['Signal'], section = 'Signal quality') 
    report_filename = os.path.join(subj_path,basename + "-report_NEW.html")
    print report_filename
    report.save(report_filename, open_browser=False, overwrite=True)
        
        
    ### 3) apply ICA to raw data and save solution and report
    # check the amplitudes do not change
    raw_ica = ica.apply(raw, copy=True)

    ### save ICA solution  
    print ica_filename
    ica.save(ica_filename)

    ### 4) save data
    data_noIca,times = raw[select_sensors,:]
    data,times       = raw_ica[select_sensors,:]

    print data.shape
    print raw.info['sfreq']

    ts_file = os.path.abspath(basename +"_ica.npy")
    np.save(ts_file,data)

    if is_sensor_space:
        return ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']
    else:
        return raw_ica, ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']

def preprocess_ts(ts_file,orig_channel_names_file,orig_channel_coords_file, h_freq, orig_sfreq, down_sfreq,prefiltered = False):
    
    from mne.io import RawArray	
	
    from mne import create_info
	
    import os
    import numpy as np

    #### load electrode names
    elec_names = [line.strip() for line in open(orig_channel_names_file)]
	#print elec_names

	### save electrode locations
    elec_loc = np.loadtxt(orig_channel_coords_file)
	#print elec_loc

    ### no modification on electrode names and locations
    correct_elec_loc = elec_loc
    correct_elec_names = elec_names
    
    print len(correct_elec_names)
    print len(correct_elec_loc)
        
        
    ### save electrode locations	
    channel_coords_file = os.path.abspath("correct_channel_coords.txt")
    np.savetxt(channel_coords_file ,correct_elec_loc , fmt = '%s')
    
    	#### save electrode names
    channel_names_file = os.path.abspath("correct_channel_names.txt")
    np.savetxt(channel_names_file,correct_elec_names , fmt = '%s')

        

        ##### downsampling on data
    ts = np.load(ts_file)
        
    print ts.shape
        
        
    raw = RawArray(ts, info = create_info(ch_names = elec_names, sfreq = orig_sfreq))
        
    indexes_good_elec = np.arange(len(elec_names))
        
    print indexes_good_elec
        
    if prefiltered == False:
        raw.filter(l_freq = None, h_freq = down_sfreq, picks = indexes_good_elec)

    raw.resample(sfreq = down_sfreq,npad = 100)
	
    downsampled_ts,times = raw[:,:]


    print downsampled_ts.shape
        
        
    downsampled_ts_file = os.path.abspath("downsampled_ts.npy")

    np.save(downsampled_ts_file,downsampled_ts)

    print raw.info['sfreq']
       
    return downsampled_ts_file,channel_coords_file,channel_names_file,raw.info['sfreq']



