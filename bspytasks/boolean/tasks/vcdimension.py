import os
import torch
import matplotlib.pyplot as plt

from bspytasks.boolean.tasks.classifier import boolean_task
from bspytasks.boolean.data import generate_targets
from brainspy.utils.io import create_directory, create_directory_timestamp
from brainspy.utils.pytorch import TorchUtils


def vc_dimension_test(
    configs,
    custom_model,
    criterion,
    algorithm,
    data_transforms=None,
    waveform_transforms=None,
    logger=None,
    is_main=True,
):
    print("---------------------------------------------")
    print(f"\tVC DIMENSION {str(configs['current_dimension'])}\t")
    print("---------------------------------------------")
    # REMOVE THIS

    configs["algorithm"]["stop_threshold"] = (
        1 - (configs["threshold_parameter"] / configs["current_dimension"])
    )  # * 100.0
    targets = generate_targets(configs["current_dimension"])
    accuracies = torch.zeros(len(targets))
    performances = torch.zeros(len(targets), configs["algorithm"]["epochs"])
    veredicts = torch.zeros(len(targets))
    correlations = torch.zeros(len(targets))

    base_dir = init_dirs(
        configs["current_dimension"], configs["results_base_dir"], is_main=is_main
    )
    configs["results_base_dir"] = base_dir
    for i in range(len(targets)):
        if logger is not None:
            logger.gate = str(targets[i])
        configs["gate"] = targets[i]
        results = boolean_task(
            configs,
            custom_model,
            criterion,
            algorithm,
            data_transforms=data_transforms,
            waveform_transforms=waveform_transforms,
            logger=logger,
            is_main=False,
        )
        if "accuracy" in results:
            accuracies[i] = results["accuracy"]["accuracy_value"]
        performances[i][:len(results['training_data']['performance_history'][0])] = results['training_data']['performance_history'][0]  # Only training performance is relevant for the boolean task, at position [0]. Since the algorithm sometimes stop because it reaches a threshold, it will only fill existing values and the rest will remain to zero.
        veredicts[i] = results["veredict"]
        correlations[i] = results["correlation"]
        del results
    results = {
        "capacity": torch.mean(veredicts),
        "threshold": configs["algorithm"]["stop_threshold"],
        "targets": targets,
        "accuracies": accuracies,
        "performances": performances,
        "veredicts": veredicts,
        "correlations": correlations,
    }
    plot_results(results, base_dir=base_dir)
    torch.save(
        results,
        os.path.join(
            base_dir, "vcdim_" + str(configs["current_dimension"]) + ".pickle"
        ),
    )
    return results


def init_dirs(dimension, base_dir, is_main):
    results_folder_name = "vc_dimension_" + str(dimension)
    if is_main:
        base_dir = create_directory_timestamp(base_dir, results_folder_name)
        create_directory(base_dir)
    else:
        base_dir = os.path.join(base_dir, results_folder_name)
        create_directory(base_dir)
    return base_dir


def plot_results(results, base_dir=None, show_plots=False):
    fig = plt.figure()
    correlations = TorchUtils.get_numpy_from_tensor(torch.abs(results["correlations"]))
    threshold = TorchUtils.get_numpy_from_tensor(
        results["threshold"] * torch.ones(correlations.shape)
    )
    accuracies = TorchUtils.get_numpy_from_tensor(results["accuracies"])
    plt.plot(correlations, threshold, "k")
    plt.scatter(correlations, accuracies)
    plt.xlabel("Fitness / Performance")
    plt.ylabel("Accuracy")

    # create_directory(path)
    plt.savefig(os.path.join(base_dir, "fitness_vs_accuracy.png"))
    if show_plots:
        plt.show()
    plt.close()
    return fig


if __name__ == "__main__":
    import datetime as d
    from torchvision import transforms

    from brainspy.utils import manager
    from bspytasks.boolean.logger import Logger
    from brainspy.utils.io import load_configs
    from brainspy.utils.transforms import (
        DataToTensor,
        DataPointsToPlateau,
        DataToVoltageRange,
    )
    from brainspy.processors.dnpu import DNPU

    V_MIN = [-1.2, -1.2]
    V_MAX = [0.6, 0.6]

    configs = load_configs("configs/boolean.yaml")
    data_transforms = transforms.Compose(
        [DataToVoltageRange(V_MIN, V_MAX, -1, 1), DataToTensor()]
    )

    waveform_transforms = transforms.Compose(
        [DataPointsToPlateau(configs["processor"]["data"]["waveform"])]
    )

    criterion = manager.get_criterion(configs["algorithm"])
    algorithm = manager.get_algorithm(configs["algorithm"])

    configs["current_dimension"] = 4
    results = vc_dimension_test(
        configs,
        DNPU,
        criterion,
        algorithm,
        data_transforms=data_transforms,
        waveform_transforms=waveform_transforms,
    )
