# %%
 
import pytorch_forecasting
from src.grabber import DataGrabber
from unicorn_binance_rest_api import BinanceRestApiManager
from auxiliary_functions import *
from src import *
# %%
sym = "ADABUSD"
tf = "5m"
# %%
client, k, s = make_client()
# %%
grabber = DataGrabber(client)
# %%



# %%
import pytorch_lightning as pl
from pytorch_lightning.callbacks import EarlyStopping, LearningRateMonitor

from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer

# %%

# %%
candles_df = grabber.get_data(symbol=sym, tframe="5m")
indicators = grabber.compute_indicators(candles_df.close)[["MACD_12_26_9", "MACDh_12_26_9", "MACDs_12_26_9"]]
candles = candles_df[['high', 'low', 'close', 'volume']]
data = pd.concat([candles, indicators], axis = 1)
data = data.iloc[33:]
data.index = range(0, 467)
# %%

  
data["time_index"] = data.index 
# %%
data
# %%
data.time_index.max()
 
# %%

  
# define dataset
max_encoder_length = 12
max_prediction_length = 3
training_cutoff = data.time_index.max() - max_prediction_length  # day for cutoff

# %%
   
training = TimeSeriesDataSet(
    data[lambda x: x.time_index < training_cutoff],
    time_idx="time_index",
    target= "close",
    # weight="weight",
    group_ids=['high', 'low', 'volume', "MACD_12_26_9", "MACDh_12_26_9", "MACDs_12_26_9"],
    min_encoder_length=0,
    max_encoder_length=max_encoder_length,
    max_prediction_length=max_prediction_length,
    # time_varying_known_reals=["time_index"],
    time_varying_unknown_reals=["close", 'high', 'low', 'volume', "MACD_12_26_9", "MACDh_12_26_9", "MACDs_12_26_9"],
)

# %%

 

# create validation and training dataset
validation = TimeSeriesDataSet.from_dataset(training, data, min_prediction_idx=training.index.time.max() + 1, stop_randomization=True)
batch_size = 128
train_dataloader = training.to_dataloader(train=True, batch_size=batch_size, num_workers=2)
val_dataloader = validation.to_dataloader(train=False, batch_size=batch_size, num_workers=2)
# %%

 
# define trainer with early stopping
early_stop_callback = EarlyStopping(monitor="val_loss", min_delta=1e-4, patience=1, verbose=False, mode="min")
lr_logger = LearningRateMonitor()
trainer = pl.Trainer(
    max_epochs=100,
    gpus=0,
    gradient_clip_val=0.1,
    limit_train_batches=30,
    callbacks=[lr_logger, early_stop_callback],
)

# create the model
tft = TemporalFusionTransformer.from_dataset(
    training,
    learning_rate=0.03,
    hidden_size=32,
    attention_head_size=1,
    dropout=0.1,
    hidden_continuous_size=16,
    output_size=7,
    loss=QuantileLoss(),
    log_interval=2,
    reduce_on_plateau_patience=4
)
print(f"Number of parameters in network: {tft.size()/1e3:.1f}k")

# find optimal learning rate (set limit_train_batches to 1.0 and log_interval = -1)
res = trainer.tuner.lr_find(
    tft, train_dataloader=train_dataloader, val_dataloaders=val_dataloader, early_stop_threshold=1000.0, max_lr=0.3,
)

print(f"suggested learning rate: {res.suggestion()}")
fig = res.plot(show=True, suggest=True)
fig.show()

# fit the model
trainer.fit(
    tft, train_dataloader=train_dataloader, val_dataloaders=val_dataloader,
 
# %%
