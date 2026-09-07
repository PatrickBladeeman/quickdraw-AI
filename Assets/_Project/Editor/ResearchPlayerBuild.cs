using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace QuickDraw.Editor
{
    internal static class ResearchPlayerBuild
    {
        internal static string GetCommandLineValue(string argumentName)
        {
            string[] arguments = Environment.GetCommandLineArgs();
            for (int index = 0; index < arguments.Length - 1; index++)
            {
                if (string.Equals(
                        arguments[index],
                        argumentName,
                        StringComparison.Ordinal))
                {
                    return arguments[index + 1];
                }
            }

            return null;
        }

        internal static void BuildWindows(
            string scenePath,
            string outputPath,
            string outputName,
            string reportName)
        {
            string absoluteOutput = Path.GetFullPath(outputPath);
            string outputDirectory = Path.GetDirectoryName(absoluteOutput);
            if (string.IsNullOrEmpty(outputDirectory))
            {
                throw new InvalidOperationException(
                    $"{outputName} build output has no directory.");
            }

            Directory.CreateDirectory(outputDirectory);
            BuildReport report = BuildPipeline.BuildPlayer(
                new BuildPlayerOptions
                {
                    scenes = new[] { scenePath },
                    locationPathName = absoluteOutput,
                    target = BuildTarget.StandaloneWindows64,
                    options = BuildOptions.None
                });

            if (report.summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    $"Research {reportName} build failed: {report.summary.result} " +
                    $"({report.summary.totalErrors} errors).");
            }

            Debug.Log(
                $"Research {reportName} build succeeded at {absoluteOutput} " +
                $"({report.summary.totalSize} bytes).");
        }
    }
}
