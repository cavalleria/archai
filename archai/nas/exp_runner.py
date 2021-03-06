# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Optional, Type, Tuple
from abc import ABC, abstractmethod
import shutil
import os

from overrides import EnforceOverrides

from archai.nas.cell_builder import CellBuilder
from archai.nas.arch_trainer import TArchTrainer
from archai.common.common import common_init
from archai.common import utils
from archai.common.config import Config
from archai.nas import evaluate
from archai.nas.search import Search
from archai.nas.finalizers import Finalizers
from archai.common.common import get_conf
from archai.nas.random_finalizers import RandomFinalizers


class ExperimentRunner(ABC, EnforceOverrides):
    def __init__(self, config_filename:str, base_name:str, toy:bool) -> None:
        self.toy_config_filename = 'confs/toy.yaml' if toy else None
        self.config_filename = config_filename
        self.base_name = base_name

    def run_search(self)->Config:
        conf = self._init('search')
        conf_search = conf['nas']['search']
        self._run_search(conf_search)
        return conf

    def _run_search(self, conf_search:Config)->None:
        cell_builder = self.cell_builder()
        trainer_class = self.trainer_class()
        finalizers = self.finalizers()

        search = Search(conf_search, cell_builder, trainer_class, finalizers)
        search.generate_pareto()

    def _init(self, suffix:str)->Config:
        config_filename = self.config_filename
        if self.toy_config_filename:
            config_filename += ';' + self.toy_config_filename

        conf = common_init(config_filepath=config_filename,
            param_args=['--common.experiment_name', self.base_name + f'_{suffix}',
                        ])
        return conf

    def _run_eval(self, conf_eval:Config)->None:
        evaluate.eval_arch(conf_eval, cell_builder=self.cell_builder())

    def run_eval(self)->Config:
        conf = self._init('eval')
        conf_eval = conf['nas']['eval']
        self._run_eval(conf_eval)
        return conf

    def _copy_final_desc(self, search_conf)->Tuple[Config, Config]:
        # get desc file path that search has produced
        search_desc_filename = search_conf['nas']['search']['final_desc_filename']
        search_desc_filepath = utils.full_path(search_desc_filename)
        assert search_desc_filepath and os.path.exists(search_desc_filepath)

        # get file path that eval would need
        eval_conf = self._init('eval')
        eval_desc_filename = eval_conf['nas']['eval']['final_desc_filename']
        eval_desc_filepath = utils.full_path(eval_desc_filename)
        assert eval_desc_filepath
        shutil.copy2(search_desc_filepath, eval_desc_filepath)

        return search_conf, eval_conf

    def run(self, search=True, eval=True)->Tuple[Optional[Config], Optional[Config]]:
        search_conf, eval_conf = None, None

        if search: # run search
            search_conf = self.run_search()

        if search and eval: # copy final desc from search and then run eval
            search_conf, eval_conf = self._copy_final_desc(search_conf)
            conf_eval = eval_conf['nas']['eval']
            self._run_eval(conf_eval)
        elif eval: # run eval
            eval_conf = self.run_eval()

        return search_conf, eval_conf

    @abstractmethod
    def cell_builder(self)->Optional[CellBuilder]:
        pass

    @abstractmethod
    def trainer_class(self)->TArchTrainer:
        pass

    def finalizers(self)->Finalizers:
        conf = get_conf()
        finalizer = conf['nas']['search']['finalizer']

        if not finalizer or finalizer == 'default':
            return Finalizers()
        elif finalizer == 'random':
            return RandomFinalizers()
        else:
            raise NotImplementedError
