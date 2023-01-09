# What is Dataflow

<img align="right" src="https://user-images.githubusercontent.com/426452/202270773-8569adeb-7909-4498-b9f5-185242e5680c.png" width="500" />

It's a very simple minimalistic project to clean and deploy datasets in real time using python. Its ideal for small and mid-sized organizations that want to deploy into production a data-processing solution with very few steps and cheap costs. It supports **[batch](#running-in-batch)** and **[streaming](#streaming-data-into-pipelines)** processing and it comes with a tool to [quickly test pipline](#unit-testing-your-pipeline).

Deploy in heroku in minutes, create pipelines of data with multiple python functions to clean your dataset and save it into CSV, SQL or BigQuery.

## How to use this project?

1. First, [install the project](#basic-installation-steps).
2. Create your first pipeline using the [dataflow-project-template](https://github.com/breatheco-de/dataflow-project-template).
3. Once your project and piplines are ready to be deployed into production, publish the project as a github repository.
4. Create the project inside the dataflow django `/admin/dataflow/project/add/` interface, to do so you will need the github repo URL you just created in the previous step.
5. Pull the [project code from github](https://github.com/breatheco-de/dataflow/blob/main/docs/images/pull-from-github.png?raw=true).
6. Make sure the pipeline has been properly listed in the [Pipelines List](/admin/dataflow/pipeline/).
7. The pipeline transformations are also [listed in the admin](/admin/dataflow/transformation/), make sure the "order" collumn matches what you specified in the project yml.
8. Specify the input and output datasources to be used, you can specify CSV Files, SQL Databases or Google Big Query.
9. Run your pipeline. If you have any errors while running your pipeline please refer to the [debugging section](#debugging-your-pipeline).

## Sources

Dataflow can retrieve or store datasets of information from and into CSV files, SQL Databases and Google BigQuery. New source types will be added in the future.

## Pipelines

A pipeline is all the steps needed to clean an incoming source dataset and save it into another dataset.

- One pipeline is comprised with one or many data **transformations**.
- One pipeline has one or more sources of information (in batch or streaming).
- One pipeline has one destination dataset.

### Running in Batch

By default, pipelines run in batch, which basically means that one (or more) entire dataset is sent to the transformation queue to be cleaned.

### Running as a Stream

Sometimes you need to process a single incoming item into the dataset, instead of cleaning the whole dataset again you only want to clean that single item before adding it to the dataset (one at a time). This is what we call a `stream`.

Dataflow can provide a URL endpoint that can be called every time an incoming stream will arrive.

## Basic Installation Steps

1. This project must be deployed in heroku (recommended) or any other cloud, you will need a Redis server for async processing and a Postgres Database for the whole system.
2. Once deployed, a cron job must be configured to run the command `python manage.py run_pipeline` every 10 min, this will be the lowest time delta that can be used to run a [batch pipeline](#Running-in-Batch), for example: You will not be able to run a batch pipeline every `9 min`, only `10 min` or more.

## Debugging your pipeline

1. Since pipelines are divided and atomized into transformations; it makes sense to start the debugging process by verifying which transformation failed.
2. You can check the list of the transformations for the column `status` with value `ERROR`.
3. Open the transformation and check for the `stdout` value, this is the buffer stdout that was created while running the transformation, every `print` statement, error or warning should show up here.


