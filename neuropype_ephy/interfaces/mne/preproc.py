"""Interfaces for preprocessing nodes"""

from nipype.interfaces.base import BaseInterface,\
    BaseInterfaceInputSpec, traits, TraitedSpec

from neuropype_ephy.preproc import compute_ica, preprocess_fif


class CompIcaInputSpec(BaseInterfaceInputSpec):
    """Input specification for CompIca"""
    fif_file = traits.File(exists=True,
                           desc='raw meg data in fif format',
                           mandatory=True)
    ecg_ch_name = traits.String(desc='name of ecg channel')
    eog_ch_name = traits.String(desc='name of eog channel')
    n_components = traits.Float(desc='number of ica components')


class CompIcaOutputSpec(TraitedSpec):
    """Output specification for CompIca"""
    ica_file = traits.File(exists=True,
                           desc='file with raw file in .fif',
                           mandatory=True)

    ica_sol_file = traits.File(exists=True,
                               desc='file with ica solution in .fif',
                               mandatory=True)
    ica_ts_file = traits.File(exists=True,
                              desc='file with ica components in .fif',
                              mandatory=True)

    report_file = traits.File(exists=True,
                              desc='ica report in .html',
                              mandatory=True)


class CompIca(BaseInterface):
    """Compute ICA solution on raw fif data"""
    input_spec = CompIcaInputSpec
    output_spec = CompIcaOutputSpec

    def _run_interface(self, runtime):
        fif_file = self.inputs.fif_file
        ecg_ch_name = self.inputs.ecg_ch_name
        eog_ch_name = self.inputs.eog_ch_name
        n_components = self.inputs.n_components

        ica_output = compute_ica(fif_file, ecg_ch_name,
                                 eog_ch_name, n_components)
        self.ica_file = ica_output[0]
        self.ica_sol_file = ica_output[1]
        self.ica_ts_file = ica_output[2]
        self.report_file = ica_output[3]

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['ica_file'] = self.ica_file
        outputs['ica_sol_file'] = self.ica_sol_file
        outputs['ica_ts_file'] = self.ica_ts_file
        outputs['report_file'] = self.report_file
        return outputs


class PreprocFifInputSpec(BaseInterfaceInputSpec):
    """Input specification for PreprocFif"""
    fif_file = traits.File(exists=True,
                           desc='raw meg data in fif format',
                           mandatory=True)
    l_freq = traits.Float(desc='lower bound for filtering')
    h_freq = traits.Float(desc='upper bound for filtering')
    down_sfreq = traits.Int(desc='downsampling frequency')


class PreprocFifOutputSpec(TraitedSpec):
    """Output specification for PreprocFif"""
    fif_file = traits.File(exists=True,
                           desc='.fif file',
                           mandatory=True)


class PreprocFif(BaseInterface):
    """Interface for preproc.preprocess_fif"""
    input_spec = PreprocFifInputSpec
    output_spec = PreprocFifOutputSpec

    def _run_interface(self, runtime):
        fif_file = self.inputs.fif_file
        l_freq = self.inputs.l_freq
        h_freq = self.inputs.h_freq
        down_sfreq = self.inputs.down_sfreq

        result_fif = preprocess_fif(fif_file, l_freq, h_freq, down_sfreq)

        self.fif_file = result_fif
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['fif_file'] = self.fif_file
        return outputs
