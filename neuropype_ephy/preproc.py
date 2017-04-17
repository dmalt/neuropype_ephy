"""Preprocessing functions"""


def preprocess_fif(fif_file, l_freq=None, h_freq=None, down_sfreq=None):
    """Filter and downsample data"""

    import os
    from mne.io import Raw
    from mne import pick_types
    from nipype.utils.filemanip import split_filename as split_f

    _, basename, ext = split_f(fif_file)

    raw = Raw(fif_file, preload=True)

    filt_str, down_str = '', ''

    select_sensors = pick_types(raw.info, meg=True, ref_meg=False, eeg=False)

    if l_freq or h_freq:
        raw.filter(l_freq=l_freq, h_freq=h_freq, l_trans_bandwidth='auto')
        filt_str = '_filt'

    if down_sfreq:
        raw.resample(sfreq=down_sfreq, npad='auto')
        down_str = '_dsamp'

    savename = os.path.abspath(basename + filt_str + down_str + ext)
    raw.save(savename)
    return savename


def compute_ica(fif_file, ecg_ch_name, eog_ch_name, n_components):
    """Compute ica solution"""

    import os

    import mne
    from mne.io import Raw
    from mne.preprocessing import ICA
    from mne.preprocessing import create_ecg_epochs, create_eog_epochs

    from nipype.utils.filemanip import split_filename as split_f

    subj_path, basename, ext = split_f(fif_file)

    raw = Raw(fif_file, preload=True)

    # select sensors
    select_sensors = mne.pick_types(raw.info, meg=True,
                                    ref_meg=False, exclude='bads')

    # 1) Fit ICA model using the FastICA algorithm
    # Other available choices are `infomax` or `extended-infomax`
    # We pass a float value between 0 and 1 to select n_components based on the
    # percentage of variance explained by the PCA components.

    reject = dict(mag=1e-1, grad=1e-9)
    flat = dict(mag=1e-13, grad=1e-13)

    ica = ICA(n_components=n_components, method='fastica', max_iter=500)

    ica.fit(raw, picks=select_sensors, reject=reject, flat=flat)
    # -------------------- Save ica timeseries ---------------------------- #
    ica_ts_file = os.path.abspath(basename + "_ica-tseries.fif")
    ica_src = ica.get_sources(raw)
    ica_src.save(ica_ts_file)
    ica_src = None
    # --------------------------------------------------------------------- #

    # 2) identify bad components by analyzing latent sources.
    # generate ECG epochs use detection via phase statistics

    # if we just have exclude channels we jump these steps
    n_max_ecg = 3
    n_max_eog = 2

    # check if ecg_ch_name is in the raw channels
    if ecg_ch_name in raw.info['ch_names']:
        raw.set_channel_types({ecg_ch_name: 'ecg'})
    else:
        ecg_ch_name = None

    ecg_epochs = create_ecg_epochs(raw, tmin=-0.5, tmax=0.5,
                                   picks=select_sensors,
                                   ch_name=ecg_ch_name)

    ecg_inds, ecg_scores = ica.find_bads_ecg(ecg_epochs, method='ctps')

    ecg_evoked = ecg_epochs.average()
    ecg_epochs = None

    ecg_inds = ecg_inds[:n_max_ecg]
    ica.exclude += ecg_inds

    if set(eog_ch_name.split(',')).issubset(set(raw.info['ch_names'])):
        eog_inds, eog_scores = ica.find_bads_eog(raw, ch_name=eog_ch_name)
        eog_inds = eog_inds[:n_max_eog]
        eog_evoked = create_eog_epochs(raw, tmin=-0.5, tmax=0.5,
                                       picks=select_sensors,
                                       ch_name=eog_ch_name).average()
    else:
        eog_inds = eog_scores = eog_evoked = None

    report_file = generate_report(raw=raw, ica=ica, subj_name=fif_file,
                                  basename=basename,
                                  ecg_evoked=ecg_evoked, ecg_scores=ecg_scores,
                                  ecg_inds=ecg_inds, ecg_ch_name=ecg_ch_name,
                                  eog_evoked=eog_evoked, eog_scores=eog_scores,
                                  eog_inds=eog_inds, eog_ch_name=eog_ch_name)

    report_file = os.path.abspath(report_file)

    ica_sol_file = os.path.abspath(basename + '_ica_solution.fif')

    ica.save(ica_sol_file)
    # raw_ica = ica.apply(raw)
    raw_ica_file = os.path.abspath(basename + '_ica' + ext)
    raw.save(raw_ica_file)

    return raw_ica_file, ica_sol_file, ica_ts_file, report_file


def get_raw_info(raw_fname):
    """Get info structure from raw meg data"""
    from mne.io import Raw

    raw = Raw(raw_fname, preload=True)
    return raw.info


def get_raw_sfreq(raw_fname):
    from mne.io import Raw

    raw = Raw(raw_fname, preload=True)
    return raw.info['sfreq']


def create_reject_dict(raw_info):
    """Create rejection dictionary for meg data"""

    from mne import pick_types

    picks_eog = pick_types(raw_info, meg=False, ref_meg=False, eog=True)
    picks_mag = pick_types(raw_info, meg='mag', ref_meg=False)
    picks_grad = pick_types(raw_info, meg='grad', ref_meg=False)

    reject = dict()
    if picks_mag.size != 0:
        reject['mag'] = 4e-12
    if picks_grad.size != 0:
        reject['grad'] = 4000e-13
    if picks_eog.size != 0:
        reject['eog'] = 150e-6

    return reject


def create_ts(raw_fname):
    """Create numpy timeseries from raw meg data"""

    import os
    import numpy as np

    import mne
    from mne.io import Raw

    from nipype.utils.filemanip import split_filename as split_f

    raw = Raw(raw_fname, preload=True)

    subj_path, basename, ext = split_f(raw_fname)

    select_sensors = mne.pick_types(raw.info, meg=True, ref_meg=False,
                                    exclude='bads')

    # save electrode locations
    sens_loc = [raw.info['chs'][i]['loc'][:3] for i in select_sensors]
    sens_loc = np.array(sens_loc)

    channel_coords_file = os.path.abspath("correct_channel_coords.txt")
    np.savetxt(channel_coords_file, sens_loc, fmt='%s')

    # save electrode names
    sens_names = np.array([raw.ch_names[pos] for pos in select_sensors],
                          dtype="str")

    channel_names_file = os.path.abspath("correct_channel_names.txt")
    np.savetxt(channel_names_file, sens_names, fmt='%s')

    data, times = raw[select_sensors, :]

    print data.shape

    ts_file = os.path.abspath(basename + '.npy')
    np.save(ts_file, data)
    print '\n *** TS FILE ' + ts_file + '*** \n'

    return ts_file, channel_coords_file, channel_names_file, raw.info['sfreq']


def generate_report(raw, ica, subj_name, basename,
                    ecg_evoked, ecg_scores, ecg_inds, ecg_ch_name,
                    eog_evoked, eog_scores, eog_inds, eog_ch_name):
    """Generate report for ica solution"""

    from mne.report import Report
    import numpy as np
    import os
    report = Report()

    ica_title = 'Sources related to %s artifacts (red)'
    is_show = False

    # ------------------- Generate report for ECG ------------------------ #
    fig_ecg_scores = ica.plot_scores(ecg_scores,
                                     exclude=ecg_inds,
                                     title=ica_title % 'ecg',
                                     show=is_show)

    # Pick the five largest ecg_scores and plot them
    show_picks = np.abs(ecg_scores).argsort()[::-1][:5]

    # Plot estimated latent sources given the unmixing matrix.

    # topoplot of unmixing matrix columns
    fig_ecg_comp = ica.plot_components(show_picks,
                                       title=ica_title % 'ecg',
                                       colorbar=True, show=is_show)

    # plot ECG sources + selection
    fig_ecg_src = ica.plot_sources(ecg_evoked, exclude=ecg_inds, show=is_show)
    fig = [fig_ecg_scores, fig_ecg_comp, fig_ecg_src]
    report.add_figs_to_section(fig,
                               captions=['Scores of ICs related to ECG',
                                         'TopoMap of ICs (ECG)',
                                         'Time-locked ECG sources'],
                               section='ICA - ECG')
    # -------------------- end generate report for ECG ---------------------- #

    # -------------------------- Generate report for EoG -------------------- #
    # check how many EoG ch we have
    if set(eog_ch_name.split(',')).issubset(set(raw.info['ch_names'])):
        fig_eog_scores = ica.plot_scores(eog_scores, exclude=eog_inds,
                                         title=ica_title % 'eog', show=is_show)

        report.add_figs_to_section(fig_eog_scores,
                                   captions=['Scores of ICs related to EOG'],
                                   section='ICA - EOG')

        n_eogs = np.shape(eog_scores)
        if len(n_eogs) > 1:
            n_eog0 = n_eogs[0]
            show_picks = [np.abs(eog_scores[i][:]).argsort()[::-1][:5]
                          for i in range(n_eog0)]
            for i in range(n_eog0):
                fig_eog_comp = ica.plot_components(show_picks[i][:],
                                                   title=ica_title % 'eog',
                                                   colorbar=True, show=is_show)

                fig = [fig_eog_comp]
                report.add_figs_to_section(fig,
                                           captions=['Scores of EoG ICs'],
                                           section='ICA - EOG')
        else:
            show_picks = np.abs(eog_scores).argsort()[::-1][:5]
            fig_eog_comp = ica.plot_components(show_picks,
                                               title=ica_title % 'eog',
                                               colorbar=True, show=is_show)

            fig = [fig_eog_comp]
            report.add_figs_to_section(fig, captions=['TopoMap of ICs (EOG)'],
                                       section='ICA - EOG')

        fig_eog_src = ica.plot_sources(eog_evoked,
                                       exclude=eog_inds,
                                       show=is_show)

        fig = [fig_eog_src]
        report.add_figs_to_section(fig, captions=['Time-locked EOG sources'],
                                   section='ICA - EOG')
    # ----------------- end generate report for EoG ---------- #

    ic_nums = range(ica.n_components_)
    fig = ica.plot_components(picks=ic_nums, show=False)
    report.add_figs_to_section(fig, captions=['All IC topographies'],
                               section='ICA - muscles')

    psds = []
    captions_psd = []
    ica_src = ica.get_sources(raw)
    for i_ic in ic_nums:
        fig = ica_src.plot_psd(tmax=None, picks=[i_ic], fmax=140, show=False)
        fig.set_figheight(3)
        fig.set_figwidth(5)
        psds.append(fig)
        captions_psd.append('IC #' + str(i_ic))

    report.add_figs_to_section(figs=psds, captions=captions_psd,
                               section='ICA - muscles')

    report_filename = os.path.join(basename + "-report.html")
    print '******* ' + report_filename
    report.save(report_filename, open_browser=False, overwrite=True)
    return report_filename


def create_events(raw, epoch_length):
    """Create events to split raw into epochs"""
    import numpy as np
    file_length = raw.n_times
    first_samp = raw.first_samp
    sfreq = raw.info['sfreq']
    n_samp_in_epoch = int(epoch_length * sfreq)

    n_epochs = int(file_length // n_samp_in_epoch)

    events = []
    for i_epoch in range(n_epochs):
        events.append([first_samp + i_epoch * n_samp_in_epoch, int(0), int(0)])
    events = np.array(events)
    return events


def create_epochs(fif_file, ep_length):
    """Split raw .fif file into epochs of
    length ep_length with rejection criteria

    """

    import os
    from mne.io import Raw
    from mne import Epochs
    from mne import pick_types
    from nipype.utils.filemanip import split_filename as split_f

    # flat = dict(mag=0.1e-12, grad=1e-13)
    # reject = dict(mag=6e-12, grad=25e-11)
    flat = None
    reject = None

    raw = Raw(fif_file)
    picks = pick_types(raw.info, ref_meg=False, eeg=False)
    if raw.times[-1] >= ep_length:
        events = create_events(raw, ep_length)
    else:
        raise Exception('File {} is too short!'.format(fif_file))

    epochs = Epochs(raw, events=events, tmin=0, tmax=ep_length,
                    preload=True, picks=picks, proj=False,
                    add_eeg_ref=False, flat=flat, reject=reject)

    _, base, ext = split_f(fif_file)
    savename = os.path.abspath(base + '-epo' + ext)
    epochs.save(savename)
    return savename
