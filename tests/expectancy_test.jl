using Makie, GLMakie
using Random
#%%
Makie.inline!(false)
#%%
function run_trades(initial_qty::Float64, tp::Float64, sl::Float64, N::Int64)
    bank = [initial_qty]
    cum_profit = [0.0]
    trades = [0.0]
    for i in 1:N
        direction = rand([0, 1])
        if direction == 0
            push!(bank, bank[end] += initial_qty*sl)
            push!(cum_profit, cum_profit[end] += 100*sl)
        elseif direction == 1
            push!(bank, bank[end] += initial_qty*tp)
            push!(cum_profit, cum_profit[end] += 100*tp)
        end
    end
    return bank, cum_profit        
end

#%%
bank, cumprof = run_trades(10.0, 0.045, -0.002, 200)


bank
#%%

fig = Figure()
#%%
ax1 = lines(fig[1, 1], bank)
ax1.axis.xlabel = "number of trades"
ax1.axis.ylabel = "\$"
#%%
ax2 = lines(fig[1, 2], cumprof)
ax2.axis.xlabel = "number of trades"
ax2.axis.ylabel = "cumulative profit (in %)"
#%%

function batch_trades(batchsize::Int64, initial_qty::Float64, tp::Float64, sl::Float64, N::Int64)

    bank, cumprof = run_trades(initial_qty, tp, sl, N)

    fig = Figure()
    ax1 = lines(fig[1, 1], bank)
    ax1.axis.xlabel = "number of trades"
    ax1.axis.ylabel = "\$"
    ax2 = lines(fig[1, 2], cumprof)
    ax2.axis.xlabel = "number of trades"
    ax2.axis.ylabel = "cumulative profit (in %)"

    for i in 1:batchsize

        bank, cumprof = run_trades(initial_qty, tp, sl, N)
        lines!(fig[1, 1], bank)
        lines!(fig[1, 2], cumprof)
    end

    return fig
end

#%%
fig = batch_trades(100, 10.0, 0.08, -0.001, 200)
