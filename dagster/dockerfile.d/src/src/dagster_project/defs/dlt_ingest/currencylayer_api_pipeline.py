import dlt
import pendulum
from dlt.sources.rest_api import RESTAPIConfig, rest_api_resources
from dlt.destinations import filesystem


@dlt.source
def _currencylayer_source(currencylayer_access_key=dlt.secrets.value):
    today = pendulum.today(tz="UTC")
    config: RESTAPIConfig = {
        "client": {
            "base_url": "https://api.currencylayer.com",
        },
        "resources": [
            {
                "name": "history",
                "endpoint": {
                    "path": "/historical",
                    "params": {
                        "access_key": currencylayer_access_key,
                        "source": "KRW",
                        "date": today.format("YYYY-MM-DD"),
                    },
                },
            }
        ],
    }

    yield from rest_api_resources(config)


currencylayer_source = _currencylayer_source()
currencylayer_pipeline = dlt.pipeline(
    pipeline_name="currencylayer_pipeline",
    dataset_name="currencylayer_history",
    destination=filesystem(
        bucket_url="s3://warehouse/currencylayer",
    ),
)
