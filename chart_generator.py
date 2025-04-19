import matplotlib.pyplot as plt
import datetime

def generate_chart(filepath="chart.png"):
    now = datetime.datetime.now()
    x = [i for i in range(10)]
    y = [i**2 for i in range(10)]

    plt.figure()
    plt.plot(x, y)
    plt.title(f"图表生成时间：{now.strftime('%Y-%m-%d %H:%M')}")
    plt.xlabel("X轴")
    plt.ylabel("Y轴")
    plt.savefig(filepath)
    plt.close()
    return filepath
