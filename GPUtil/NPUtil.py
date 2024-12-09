# NPUtil - NPU utilization
#
# A Python module for programmically getting the NPU utilization from Ascend NPUs using npu-smi
#


from typing import List
from subprocess import Popen, PIPE
import os
import math
import random
import time


__version__ = "1.4.0"


class NPU:
    def __init__(
        self,
        ID,
        typ,
        health,
        power,
        temp,
        hugepages,
        chip,
        bus_id,
        aicore,
        memory,
        hbm,
        hbm_total,
    ):
        self.id: int = ID
        self.typ: str = typ
        self.health: str = health
        self.hbmUtil: float = float(hbm) / float(hbm_total)
        self.hbmTotal: float = hbm_total
        self.hbmUsed: float = hbm
        self.hbmFree: float = hbm_total - hbm
        self.power: float = power
        self.temperature: float = temp
        self.hugepages: float = hugepages
        self.memory: float = memory
        self.chip: str = chip
        self.bus_id: str = bus_id
        self.aicore: float = aicore


def safeFloatCast(strNumber):
    try:
        number = float(strNumber)
    except ValueError:
        number = float("nan")
    return number


def npu_smi_to_csv(smi_output: str) -> str:
    lines = smi_output.strip().split("\n")
    csv_lines = []

    # 跳过版本信息和表头
    start_idx = 0
    for i, line in enumerate(lines):
        if "===" in line:
            start_idx = i + 1
            break

    # 解析设备信息
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()

        if "Process id" in line:
            break

        # 跳过分隔线
        if not line or "+" in line or "=" in line:
            i += 1
            continue

        # 解析当前NPU的两行信息
        first_line = line.split("|")
        second_line = lines[i + 1].split("|")

        if len(first_line) >= 4 and len(second_line) >= 4:
            # 提取第一行数据
            npu_id = first_line[1].strip().split()[0]
            npu_type = first_line[1].strip().split()[1]
            health = first_line[2].strip()
            power = first_line[3].strip().split()[0]
            temp = first_line[3].strip().split()[1]
            hugepages = first_line[3].strip().split()[-1].split("/")[0].strip()

            # 提取第二行数据
            chip = second_line[1].strip().split()[0]
            bus_id = second_line[2].strip()
            aicore = second_line[3].strip().split()[0]
            memory = second_line[3].strip().split()[1].strip()
            hbm = second_line[3].strip().split()[-2].strip().strip("/")
            hbm_total = second_line[3].strip().split()[-1].strip()

            # 组合CSV行
            csv_line = f"{npu_id},{npu_type},{health},{power},{temp},{hugepages},{chip},{bus_id},{aicore},{memory},{hbm},{hbm_total}"
            csv_lines.append(csv_line)

        i += 2

    return "\n".join(csv_lines)


def getNPUs() -> List[NPU]:
    npu_smi = "npu-smi"

    # Get ID, processing and memory utilization for all NPUs
    try:
        p = Popen([npu_smi, "info"], stdout=PIPE)
        stdout, stderror = p.communicate()
    except:
        return []

    output = stdout.decode("UTF-8")
    output = npu_smi_to_csv(output)

    ## Parse output
    lines = output.split(os.linesep)
    numDevices = len(lines) - 1
    NPUs = []
    for g in range(numDevices):
        line = lines[g]
        vals = line.split(",")
        for i in range(12):
            if i == 0:
                npu_id = int(vals[i])
            elif i == 1:
                npu_type = vals[i]
            elif i == 2:
                health = vals[i]
            elif i == 3:
                power = safeFloatCast(vals[i])
            elif i == 4:
                temp = safeFloatCast(vals[i])
            elif i == 5:
                hugepages = safeFloatCast(vals[i])
            elif i == 6:
                chip = vals[i]
            elif i == 7:
                bus_id = vals[i]
            elif i == 8:
                aicore = safeFloatCast(vals[i])
            elif i == 9:
                memory = safeFloatCast(vals[i])
            elif i == 10:
                hbm = safeFloatCast(vals[i])
            elif i == 11:
                hbm_total = safeFloatCast(vals[i])
        NPUs.append(
            NPU(
                npu_id,
                npu_type,
                health,
                power,
                temp,
                hugepages,
                chip,
                bus_id,
                aicore,
                memory,
                hbm,
                hbm_total,
            )
        )
    return NPUs


def getAvailable(
    order="first",
    limit=1,
    maxLoad=0.5,
    maxMemory=0.5,
    memoryFree=0,
    includeNan=False,
    excludeID=[],
    excludeBusID=[],
) -> List[int]:
    # order = first | last | random | load | memory
    #    first --> select the NPU with the lowest ID (DEFAULT)
    #    last --> select the NPU with the highest ID
    #    random --> select a random available NPU
    #    memory --> select the NPU with the most memory available
    # limit = 1 (DEFAULT), 2, ..., Inf
    #     Limit sets the upper limit for the number of NPUs to return. E.g. if limit = 2, but only one is available, only one is returned.

    # Get device IDs, load and memory usage
    NPUs = getNPUs()

    # Determine, which NPUs are available
    NPUavailability = getAvailability(
        NPUs,
        maxLoad=maxLoad,
        maxHbmUtil=maxMemory,
        hbmFree=memoryFree,
        includeNan=includeNan,
        excludeID=excludeID,
        excludeBusID=excludeBusID,
    )
    availAbleNPUindex = [
        idx for idx in range(0, len(NPUavailability)) if (NPUavailability[idx] == 1)
    ]
    # Discard unavailable NPUs
    NPUs = [NPUs[g] for g in availAbleNPUindex]

    # Sort available NPUs according to the order argument
    if order == "first":
        NPUs.sort(
            key=lambda x: float("inf") if math.isnan(x.id) else x.id, reverse=False
        )
    elif order == "last":
        NPUs.sort(
            key=lambda x: float("-inf") if math.isnan(x.id) else x.id, reverse=True
        )
    elif order == "random":
        NPUs = [NPUs[g] for g in random.sample(range(0, len(NPUs)), len(NPUs))]
    elif order == "memory":
        NPUs.sort(
            key=lambda x: float("inf") if math.isnan(x.hbmUtil) else x.hbmUtil,
            reverse=False,
        )

    # Extract the number of desired NPUs, but limited to the total number of available NPUs
    NPUs = NPUs[0 : min(limit, len(NPUs))]

    # Extract the device IDs from the NPUs and return them
    deviceIds = [npu.id for npu in NPUs]

    return deviceIds


def getAvailability(
    NPUs: List[NPU],
    maxLoad=0.5,
    maxHbmUtil=0.5,
    hbmFree=0,
    includeNan=False,
    excludeID=[],
    excludeBusID=[],
):
    # Determine, which NPUs are available
    NPUavailability = [
        1
        if (npu.hbmFree >= hbmFree)
        and (npu.aicore < maxLoad * 100 or (includeNan and math.isnan(npu.aicore)))
        and (npu.hbmUtil < maxHbmUtil or (includeNan and math.isnan(npu.hbmUtil)))
        and ((npu.id not in excludeID) and (npu.bus_id not in excludeBusID))
        else 0
        for npu in NPUs
    ]
    return NPUavailability


def getFirstAvailable(
    order="first",
    maxLoad=0.5,
    maxMemory=0.5,
    attempts=1,
    interval=900,
    verbose=False,
    includeNan=False,
    excludeID=[],
    excludeBusID=[],
):
    for i in range(attempts):
        if verbose:
            print(
                "Attempting ("
                + str(i + 1)
                + "/"
                + str(attempts)
                + ") to locate available NPU."
            )
        # Get first available NPU
        available = getAvailable(
            order=order,
            limit=1,
            maxLoad=maxLoad,
            maxMemory=maxMemory,
            includeNan=includeNan,
            excludeID=excludeID,
            excludeBusID=excludeBusID,
        )
        # If an available NPU was found, break for loop.
        if available != []:
            if verbose:
                print("NPU " + str(available) + " located!")
            break
        # If this is not the last attempt, sleep for 'interval' seconds
        if i != attempts - 1:
            time.sleep(interval)

    # Check if an NPU was found, or if the attempts simply ran out. Throw error, if no NPU was found
    if not (available):
        raise RuntimeError(
            "Could not find an available NPU after "
            + str(attempts)
            + " attempts with "
            + str(interval)
            + " seconds interval."
        )

    # Return found NPU
    return available


def showUtilization(all=False, attrList=None, useOldCode=False):
    NPUs = getNPUs()
    if all:
        if useOldCode:
            print(
                " ID | Type | Chip | BusID || Power | HBM util. | AICore || HBM total | HBM used | HBM free |"
            )
            print(
                "--------------------------------------------------------------------------------------------------"
            )
            for npu in NPUs:
                print(
                    " {0:2d} | {1:s}  | {2:s} | {3:s} || {4:3.0f} | {5:3.0f}% | {6:3.0f} || {7:.0f}MB | {8:.0f}MB | {9:.0f}MB |".format(
                        npu.id,
                        npu.typ,
                        npu.chip,
                        npu.bus_id,
                        npu.power,
                        npu.hbmUtil * 100,
                        npu.aicore,
                        npu.hbmTotal,
                        npu.hbmUsed,
                        npu.hbmFree,
                    )
                )
        else:
            attrList = [
                [
                    {"attr": "id", "name": "ID"},
                    {"attr": "typ", "name": "Type"},
                    {"attr": "chip", "name": "Chip"},
                    {"attr": "bus_id", "name": "BusID"},
                ],
                [
                    {
                        "attr": "power",
                        "name": "Power",
                        "suffix": "W",
                        "transform": lambda x: x,
                        "precision": 0,
                    },
                    {
                        "attr": "hbmUtil",
                        "name": "HBM util.",
                        "suffix": "%",
                        "transform": lambda x: x * 100,
                        "precision": 0,
                    },
                    {
                        "attr": "aicore",
                        "name": "AI-Core",
                        "suffix": "%",
                        "transform": lambda x: x,
                        "precision": 0,
                    },
                ],
                [
                    {
                        "attr": "hbmTotal",
                        "name": "HBM total",
                        "suffix": "MB",
                        "precision": 0,
                    },
                    {
                        "attr": "hbmUsed",
                        "name": "HBM used",
                        "suffix": "MB",
                        "precision": 0,
                    },
                    {
                        "attr": "hbmFree",
                        "name": "HBM free",
                        "suffix": "MB",
                        "precision": 0,
                    },
                ],
            ]

    else:
        if useOldCode:
            print(" ID   NPU  MEM")
            print("---------------")
            for npu in NPUs:
                print(
                    " {0:2d} {1:4.0f}% {2:3.0f}%".format(
                        npu.id, npu.power, npu.memoryUtil * 100
                    )
                )
        elif attrList is None:
            # if `attrList` was not specified, use the default one
            attrList = [
                [
                    {"attr": "id", "name": "ID"},
                    {
                        "attr": "aicore",
                        "name": "NPU",
                        "suffix": "%",
                        "transform": lambda x: x,
                        "precision": 0,
                    },
                    {
                        "attr": "hbmUtil",
                        "name": "MEM",
                        "suffix": "%",
                        "transform": lambda x: x * 100,
                        "precision": 0,
                    },
                ],
            ]

    if not useOldCode:
        if attrList is not None:
            headerString = ""
            NPUstrings = [""] * len(NPUs)
            for attrGroup in attrList:
                # print(attrGroup)
                for attrDict in attrGroup:
                    headerString = headerString + "| " + attrDict["name"] + " "
                    headerWidth = len(attrDict["name"])
                    minWidth = len(attrDict["name"])

                    attrPrecision = (
                        "." + str(attrDict["precision"])
                        if ("precision" in attrDict.keys())
                        else ""
                    )
                    attrSuffix = (
                        str(attrDict["suffix"]) if ("suffix" in attrDict.keys()) else ""
                    )
                    attrTransform = (
                        attrDict["transform"]
                        if ("transform" in attrDict.keys())
                        else lambda x: x
                    )
                    for npu in NPUs:
                        attr = getattr(npu, attrDict["attr"])

                        attr = attrTransform(attr)

                        if isinstance(attr, float):
                            attrStr = ("{0:" + attrPrecision + "f}").format(attr)
                        elif isinstance(attr, int):
                            attrStr = ("{0:d}").format(attr)
                        elif isinstance(attr, str):
                            attrStr = attr
                        else:
                            raise TypeError(
                                "Unhandled object type ("
                                + str(type(attr))
                                + ") for attribute '"
                                + attrDict["name"]
                                + "'"
                            )

                        attrStr += attrSuffix

                        minWidth = max(minWidth, len(attrStr))

                    headerString += " " * max(0, minWidth - headerWidth)

                    minWidthStr = str(minWidth - len(attrSuffix))

                    for npuIdx, npu in enumerate(NPUs):
                        attr = getattr(npu, attrDict["attr"])

                        attr = attrTransform(attr)

                        if isinstance(attr, float):
                            attrStr = (
                                "{0:" + minWidthStr + attrPrecision + "f}"
                            ).format(attr)
                        elif isinstance(attr, int):
                            attrStr = ("{0:" + minWidthStr + "d}").format(attr)
                        elif isinstance(attr, str):
                            attrStr = ("{0:" + minWidthStr + "s}").format(attr)
                        else:
                            raise TypeError(
                                "Unhandled object type ("
                                + str(type(attr))
                                + ") for attribute '"
                                + attrDict["name"]
                                + "'"
                            )

                        attrStr += attrSuffix

                        NPUstrings[npuIdx] += "| " + attrStr + " "

                headerString = headerString + "|"
                for npuIdx, npu in enumerate(NPUs):
                    NPUstrings[npuIdx] += "|"

            headerSpacingString = "-" * len(headerString)
            print(headerString)
            print(headerSpacingString)
            for NPUstring in NPUstrings:
                print(NPUstring)
