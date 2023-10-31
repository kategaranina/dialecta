import os
import json
import random
from pathlib import Path
from collections import defaultdict

import torch
import click
import evaluate
import numpy as np
from tqdm import tqdm
from torch.utils.data import DataLoader
from datasets import Dataset, DatasetDict
from transformers import (
    AutoModelForSeq2SeqLM, AutoTokenizer,
    DataCollatorForSeq2Seq, Seq2SeqTrainingArguments,
    Seq2SeqTrainer, GenerationConfig
)
from transformers.integrations import NeptuneCallback


SEED = 42
ROOT_DIR = Path(__file__).parent
TMP_DIR = os.environ.get('TMPDIR', ROOT_DIR)

MAX_LENGTH = 512
LABEL_PAD_TOKEN_ID = -100


random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

DEV_METRIC = evaluate.load("chrf")


def preprocess_data(ds, tokenizer):
    def tokenize(examples):
        model_inputs = tokenizer(examples['input'], max_length=MAX_LENGTH, truncation=True)
        if 'output' in examples:
            labels = tokenizer(text_target=examples['output'], max_length=MAX_LENGTH, truncation=True)
            model_inputs['labels'] = labels['input_ids']
        return model_inputs

    ds = ds.map(tokenize, batched=True)
    return ds


def decode_preds(preds, tokenizer):
    decoded_preds = tokenizer.batch_decode(
        preds,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )
    return decoded_preds


def decode_labels(labels, tokenizer):
    labels = np.where(labels != LABEL_PAD_TOKEN_ID, labels, tokenizer.pad_token_id)
    decoded_labels = tokenizer.batch_decode(
        labels,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )
    return decoded_labels


def postprocess_text(preds, labels):
    preds = [pred.strip() for pred in preds]
    labels = [[label.strip()] for label in labels]
    return preds, labels


def evaluate_preds(preds, labels):
    # Some simple post-processing
    preds, labels = postprocess_text(preds, labels)
    result = DEV_METRIC.compute(predictions=preds, references=labels)
    result = {"chrf": result["score"]}
    return result


def run_eval_step(eval_preds, tokenizer):
    preds, labels = eval_preds
    if isinstance(preds, tuple):
        preds = preds[0]

    decoded_preds = decode_preds(preds, tokenizer)
    decoded_labels = decode_labels(labels, tokenizer)
    score = evaluate_preds(decoded_preds, decoded_labels)

    # for p, l in zip(decoded_preds[:10], decoded_labels[:10]):
    #     print(l)
    #     print(p)
    #     print()

    return score


def run_prediction(dataset, model, tokenizer, model_dir, batch_size, data_part, generation_params):
    model.eval()

    collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        label_pad_token_id=LABEL_PAD_TOKEN_ID
    )

    if generation_params['do_sample']:
        batch_size = 1  # for deterministic generation when sampling

    tokens = dataset.remove_columns([c for c in dataset.column_names if c not in tokenizer.model_input_names])
    test_dataloader = DataLoader(tokens, batch_size=batch_size, collate_fn=collator)

    all_preds = []

    with torch.no_grad():
        for batch in tqdm(test_dataloader):
            # for deterministic generation when sampling
            random.seed(SEED)
            np.random.seed(SEED)
            torch.manual_seed(SEED)

            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            preds = model.generate(
                **batch,
                **generation_params,
                max_length=MAX_LENGTH
            )
            decoded_preds = decode_preds(preds, tokenizer)
            all_preds.extend(decoded_preds)

    assert len(all_preds) == len(dataset['recording'])

    preds_by_recording = defaultdict(list)
    for pred, dataset_item in zip(all_preds, dataset):
        preds_by_recording[dataset_item['recording']].append({
            'speaker': dataset_item['speaker'],
            'input': dataset_item['input'].replace(' | ', ' '),
            'pred': pred.replace(' | ', ' '),
            'old_output': dataset_item.get('old_output')
        })

    params_str = '_'.join(f'{k.replace("_", "-")}{v}' for k, v in generation_params.items())
    with open(os.path.join(model_dir, 'preds', f'preds_{params_str}_{data_part}.jsonl'), 'w') as f:
        json.dump(preds_by_recording, f, ensure_ascii=False, indent=2)

    if 'output' in dataset:
        scores = evaluate_preds(all_preds, [[v] for v in dataset['output']])
        str_scores = '\n'.join(f'{k}: {v}' for k, v in scores.items())
        print('FINAL SCORE', str_scores)


@click.command()
# @click.option("--do-train", is_flag=True, help="Run training")
# @click.option("--do-predict", is_flag=True, type=bool, help="Run prediction on the best model")
# @click.option("--do-ckpt-predict", is_flag=True, type=bool, help="Run prediction for dev on available checkpoints.")
# @click.option("--source", default="all", type=str, help="Source of data - main, generated, or all.")
@click.option("--base-model", default="t5-small", type=str, help="Base model to finetune")
@click.option("--epochs", default=30, type=int, help="Maximum number of epochs")
@click.option("--batch-size", default=16, type=int, help="Path to the output directory")
@click.option("--learning-rate", default=1e-4, type=float, help="Learning rate")
@click.option("--eval-steps", default=0, type=int, help="Training steps before evaluation. If 0, evaluation after every epoch.")
@click.option("--num-beams", default=1, type=int, help="Number of beams for generation.")
@click.option("--temperature", default=1.0, type=float, help="Generation temperature.")
@click.option("--do-sample", is_flag=True, help="Whether to do sampling.")
@click.option("--top-k", default=50, type=int, help="Top k for sampling.")
@click.option("--ckpt-dir", default=os.path.join(TMP_DIR, "checkpoints"), type=str, help="Directory to store checkpoints")
@click.option("--output-dir", default=os.path.join(ROOT_DIR, "models"), type=str, help="Directory to store models and their outputs")
def main(
        # do_train, do_predict, do_ckpt_predict, source,
        base_model,
        epochs, batch_size, learning_rate, eval_steps,
        num_beams, temperature, do_sample, top_k,
        ckpt_dir, output_dir
):
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    model_name = f'dialecta_{base_model.rsplit("/", 1)[-1]}_{epochs}e_{batch_size}bs'

    save_dir = os.path.join(output_dir, model_name)
    model_ckpt_dir = os.path.join(ckpt_dir, model_name)
    model_save_dir = os.path.join(save_dir, "model")

    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(os.path.join(save_dir, "preds"), exist_ok=True)
    os.makedirs(os.path.join(save_dir, "scores"), exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(base_model)

    with open(os.path.join(ROOT_DIR, 'annotation_data.json')) as f:
        data = json.load(f)

    ds = DatasetDict({
        part: Dataset.from_list(items)
        for part, items in data.items()
    })
    ds = preprocess_data(ds, tokenizer)
    ds_train = ds['train'].train_test_split(test_size=0.1, seed=SEED)
    ds['train'] = ds_train['train']
    ds['dev'] = ds_train['test']

    generation_params = {
        'num_beams': num_beams,
        'temperature': temperature,
        'do_sample': do_sample,
        'top_k': top_k
    }

    def compute_dev_metrics(eval_preds):
        return run_eval_step(eval_preds, tokenizer)

    # neptune_callback = NeptuneCallback(
    #     tags=[model_name],
    #     project="kategaranina/content-selection"
    # )
    # neptune_callback.run['model'] = model_name
    # neptune_callback.run['source'] = source
    # neptune_callback.run['base_model'] = base_model
    # neptune_callback.run['parameters/batch_size'] = batch_size
    # neptune_callback.run['parameters/learning_rate'] = learning_rate
    # neptune_callback.run['parameters/eval_steps'] = eval_steps

    print(f'Fine-tuning {model_name}')
    # neptune_callback.run['mode/train'] = True

    model = AutoModelForSeq2SeqLM.from_pretrained(base_model)
    ds['train'] = ds['train'].shuffle(seed=SEED)
    print(ds)

    collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        label_pad_token_id=LABEL_PAD_TOKEN_ID
    )

    if eval_steps > 0:
        eval_params = {
            'evaluation_strategy': 'steps',
            'eval_steps': eval_steps,
            'save_strategy': 'steps',
            'save_steps': eval_steps
        }
    else:
        eval_params = {
            'evaluation_strategy': 'epoch',
            'save_strategy': 'epoch',
        }

    training_args = Seq2SeqTrainingArguments(
        output_dir=model_ckpt_dir,
        report_to='none',
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        num_train_epochs=epochs,
        predict_with_generate=True,
        generation_max_length=MAX_LENGTH,
        metric_for_best_model='eval_chrf',
        greater_is_better=True,
        load_best_model_at_end=True,
        **eval_params
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=ds['train'],
        eval_dataset=ds['dev'],
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_dev_metrics
        # callbacks=[neptune_callback]
    )

    trainer.train()
    trainer.save_model(model_save_dir)

    run_prediction(
        dataset=ds['test'],
        model=trainer.model,
        tokenizer=tokenizer,
        model_dir=save_dir,
        batch_size=batch_size,
        data_part='test',
        generation_params=generation_params
    )


if __name__ == '__main__':
    main()
